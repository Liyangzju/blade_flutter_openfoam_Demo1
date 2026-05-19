#!/usr/bin/env python3
"""Export a mapped OpenFOAM blade mode to legacy VTK PolyData.

Input mapped CSV columns:
    patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance

The output VTK file uses deformed coordinates:
    x_view = x + scale * phi

It also stores the modal vector phi, its magnitude, and the original point
coordinates as point data so ParaView can inspect either the original or scaled
shape.

This script intentionally avoids newer Python syntax so it can run on older
server python3 installations.
"""

import argparse
import csv
import math
import re
from pathlib import Path


class Point(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def scale(self, value):
        return Point(self.x * value, self.y * value, self.z * value)


class PatchInfo(object):
    def __init__(self, name, n_faces, start_face):
        self.name = name
        self.n_faces = n_faces
        self.start_face = start_face


class PatchTopology(object):
    def __init__(self, point_labels, faces, points):
        self.point_labels = point_labels
        self.faces = faces
        self.points = points


class MappedMode(object):
    def __init__(self, point, phi):
        self.point = point
        self.phi = phi


def _next_count(lines, start=0):
    for i in range(start, len(lines)):
        text = lines[i].strip()
        if text.isdigit():
            return int(text), i
    raise ValueError("Could not find OpenFOAM list count")


def read_points(points_file):
    lines = points_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    n_points, count_i = _next_count(lines)

    points = []
    pattern = re.compile(r"\(\s*([^()\s]+)\s+([^()\s]+)\s+([^()\s]+)\s*\)")

    for line in lines[count_i + 1:]:
        match = pattern.search(line)
        if not match:
            continue
        values = [float(value) for value in match.groups()]
        points.append(Point(values[0], values[1], values[2]))
        if len(points) == n_points:
            break

    if len(points) != n_points:
        raise ValueError("Expected {} points, read {}".format(n_points, len(points)))

    return points


def read_faces(faces_file):
    lines = faces_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    n_faces, count_i = _next_count(lines)

    faces = []
    pattern = re.compile(r"\s*\d+\(([^()]*)\)")

    for line in lines[count_i + 1:]:
        match = pattern.match(line)
        if not match:
            continue
        faces.append([int(value) for value in match.group(1).split()])
        if len(faces) == n_faces:
            break

    if len(faces) != n_faces:
        raise ValueError("Expected {} faces, read {}".format(n_faces, len(faces)))

    return faces


def read_boundary(boundary_file):
    lines = boundary_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    patches = []

    i = 0
    while i < len(lines):
        name = lines[i].strip()
        if not name or name.startswith("/") or name in {"(", ")"}:
            i += 1
            continue

        if i + 1 >= len(lines) or lines[i + 1].strip() != "{":
            i += 1
            continue

        block_lines = []
        depth = 0
        for j in range(i + 1, len(lines)):
            text = lines[j]
            depth += text.count("{")
            depth -= text.count("}")
            block_lines.append(text)
            if depth == 0:
                block = "\n".join(block_lines)
                n_faces = re.search(r"\bnFaces\s+(\d+)\s*;", block)
                start_face = re.search(r"\bstartFace\s+(\d+)\s*;", block)
                if n_faces and start_face:
                    patches.append(
                        PatchInfo(
                            name=name,
                            n_faces=int(n_faces.group(1)),
                            start_face=int(start_face.group(1)),
                        )
                    )
                i = j + 1
                break
        else:
            i += 1

    return patches


def selected_patch_topology(case_dir, patch_regex):
    poly_mesh = case_dir / "constant" / "polyMesh"
    points = read_points(poly_mesh / "points")
    faces = read_faces(poly_mesh / "faces")
    patches = read_boundary(poly_mesh / "boundary")
    pattern = re.compile(patch_regex)

    selected = {}
    for patch in patches:
        if not pattern.fullmatch(patch.name):
            continue

        point_labels = []
        label_to_local = {}
        local_faces = []

        for face in faces[patch.start_face:patch.start_face + patch.n_faces]:
            local_face = []
            for point_label in face:
                if point_label not in label_to_local:
                    label_to_local[point_label] = len(point_labels)
                    point_labels.append(point_label)
                local_face.append(label_to_local[point_label])
            local_faces.append(local_face)

        selected[patch.name] = PatchTopology(
            point_labels=point_labels,
            faces=local_faces,
            points=[points[label] for label in point_labels],
        )

    if not selected:
        names = ", ".join(patch.name for patch in patches)
        raise ValueError("No patches matched {!r}. Available patches: {}".format(patch_regex, names))

    return selected


def read_mapped_mode(path):
    values = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(row for row in handle if not row.lstrip().startswith("#"))
        required = {"patchName", "patchPointI", "x", "y", "z", "phi_x", "phi_y", "phi_z"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError("{} missing columns: {}".format(path, ", ".join(sorted(missing))))

        for row in reader:
            key = (row["patchName"], int(row["patchPointI"]))
            values[key] = MappedMode(
                point=Point(float(row["x"]), float(row["y"]), float(row["z"])),
                phi=Point(float(row["phi_x"]), float(row["phi_y"]), float(row["phi_z"])),
            )

    if not values:
        raise ValueError("No mapped mode rows found in {}".format(path))

    return values


def magnitude(point):
    return math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z)


def write_vtk(path, topology_by_patch, mapped_mode, scale):
    path.parent.mkdir(parents=True, exist_ok=True)

    vtk_points = []
    original_points = []
    phis = []
    polygons = []
    patch_ids = []
    patch_names = []

    offset = 0
    for patch_id, patch_name in enumerate(sorted(topology_by_patch)):
        topology = topology_by_patch[patch_name]
        patch_names.append(patch_name)

        for point_i, fallback_point in enumerate(topology.points):
            value = mapped_mode.get((patch_name, point_i))
            if value is None:
                point = fallback_point
                phi = Point(0.0, 0.0, 0.0)
            else:
                point = value.point
                phi = value.phi

            original_points.append(point)
            phis.append(phi)
            vtk_points.append(point + phi.scale(scale))

        for face in topology.faces:
            polygons.append([offset + point_i for point_i in face])
            patch_ids.append(patch_id)

        offset += len(topology.points)

    polygon_size = sum(len(face) + 1 for face in polygons)

    with path.open("w", encoding="utf-8") as handle:
        handle.write("# vtk DataFile Version 3.0\n")
        handle.write("Demo3 mapped FEM mode\n")
        handle.write("ASCII\n")
        handle.write("DATASET POLYDATA\n")
        handle.write("FIELD FieldData {}\n".format(len(patch_names)))
        for patch_id, patch_name in enumerate(patch_names):
            handle.write("patch_{} 1 {} char\n".format(patch_id, len(patch_name)))
            handle.write(" ".join(str(ord(char)) for char in patch_name) + "\n")

        handle.write("POINTS {} double\n".format(len(vtk_points)))
        for point in vtk_points:
            handle.write("{:.12g} {:.12g} {:.12g}\n".format(point.x, point.y, point.z))

        handle.write("POLYGONS {} {}\n".format(len(polygons), polygon_size))
        for face in polygons:
            handle.write("{} ".format(len(face)) + " ".join(str(point_i) for point_i in face) + "\n")

        handle.write("POINT_DATA {}\n".format(len(vtk_points)))
        handle.write("VECTORS phi double\n")
        for phi in phis:
            handle.write("{:.12g} {:.12g} {:.12g}\n".format(phi.x, phi.y, phi.z))

        handle.write("VECTORS originalPosition double\n")
        for point in original_points:
            handle.write("{:.12g} {:.12g} {:.12g}\n".format(point.x, point.y, point.z))

        handle.write("SCALARS phiMag double 1\n")
        handle.write("LOOKUP_TABLE default\n")
        for phi in phis:
            handle.write("{:.12g}\n".format(magnitude(phi)))

        handle.write("CELL_DATA {}\n".format(len(polygons)))
        handle.write("SCALARS patchId int 1\n")
        handle.write("LOOKUP_TABLE default\n")
        for patch_id in patch_ids:
            handle.write("{}\n".format(patch_id))

    print("Wrote VTK mode view: {}".format(path))
    print("Points: {}".format(len(vtk_points)))
    print("Polygons: {}".format(len(polygons)))
    print("Scale: {:g}".format(scale))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path, help="OpenFOAM case directory")
    parser.add_argument("--patch-regex", default="blade.*", help="Patch regex to export")
    parser.add_argument("--mapped", required=True, type=Path, help="Mapped mode CSV")
    parser.add_argument("--out", required=True, type=Path, help="Output legacy VTK file")
    parser.add_argument("--scale", default=0.05, type=float, help="Display scale for phi")
    args = parser.parse_args()

    topology_by_patch = selected_patch_topology(args.case, args.patch_regex)
    mapped_mode = read_mapped_mode(args.mapped)
    write_vtk(args.out, topology_by_patch, mapped_mode, args.scale)


if __name__ == "__main__":
    main()
