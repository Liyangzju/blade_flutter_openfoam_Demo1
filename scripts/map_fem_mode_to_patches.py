#!/usr/bin/env python3
"""Map FEM surface mode data to one or more OpenFOAM patches.

Input FEM CSV columns:
    nodeId,x,y,z,phi_x,phi_y,phi_z

Output mapped CSV columns:
    patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance

The Demo3 propeller pointDisplacement boundary condition reads this mapped
format and selects rows by the current patch name.

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

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def scale(self, value):
        return Point(self.x * value, self.y * value, self.z * value)


class FemNode(object):
    def __init__(self, node_id, point, phi):
        self.node_id = node_id
        self.point = point
        self.phi = phi


class KdNode(object):
    def __init__(self, item, axis, left, right):
        self.item = item
        self.axis = axis
        self.left = left
        self.right = right


class PatchInfo(object):
    def __init__(self, name, n_faces, start_face):
        self.name = name
        self.n_faces = n_faces
        self.start_face = start_face


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


def patch_points(case_dir, patch_pattern):
    poly_mesh = case_dir / "constant" / "polyMesh"
    points = read_points(poly_mesh / "points")
    faces = read_faces(poly_mesh / "faces")
    patches = read_boundary(poly_mesh / "boundary")
    pattern = re.compile(patch_pattern)

    selected = {}
    for patch in patches:
        if not pattern.fullmatch(patch.name):
            continue

        point_labels = []
        seen = set()

        for face in faces[patch.start_face:patch.start_face + patch.n_faces]:
            for point_label in face:
                if point_label not in seen:
                    seen.add(point_label)
                    point_labels.append(point_label)

        selected[patch.name] = [points[label] for label in point_labels]

    if not selected:
        names = ", ".join(patch.name for patch in patches)
        raise ValueError("No patches matched {!r}. Available patches: {}".format(patch_pattern, names))

    return selected


def read_fem_csv(path):
    nodes = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(row for row in handle if not row.lstrip().startswith("#"))
        required = {"nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError("{} missing columns: {}".format(path, ", ".join(sorted(missing))))

        for row in reader:
            nodes.append(
                FemNode(
                    node_id=row["nodeId"],
                    point=Point(float(row["x"]), float(row["y"]), float(row["z"])),
                    phi=Point(float(row["phi_x"]), float(row["phi_y"]), float(row["phi_z"])),
                )
            )

    if not nodes:
        raise ValueError("No FEM nodes found in {}".format(path))

    return nodes


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def mag(a):
    return math.sqrt(dot(a, a))


def distance2(a, b):
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2


def coordinate(point, axis):
    if axis == 0:
        return point.x
    if axis == 1:
        return point.y
    return point.z


def build_kd_tree(nodes, depth=0):
    if not nodes:
        return None

    axis = depth % 3
    nodes = sorted(nodes, key=lambda node: coordinate(node.point, axis))
    mid = len(nodes) // 2
    return KdNode(
        item=nodes[mid],
        axis=axis,
        left=build_kd_tree(nodes[:mid], depth + 1),
        right=build_kd_tree(nodes[mid + 1:], depth + 1),
    )


def nearest_in_kd_tree(target, tree, best, best_distance2):
    if tree is None:
        return best, best_distance2

    item_distance2 = distance2(target, tree.item.point)
    if item_distance2 < best_distance2:
        best = tree.item
        best_distance2 = item_distance2

    diff = coordinate(target, tree.axis) - coordinate(tree.item.point, tree.axis)
    near_branch = tree.left if diff < 0 else tree.right
    far_branch = tree.right if diff < 0 else tree.left

    best, best_distance2 = nearest_in_kd_tree(target, near_branch, best, best_distance2)
    if diff * diff < best_distance2:
        best, best_distance2 = nearest_in_kd_tree(target, far_branch, best, best_distance2)

    return best, best_distance2


def normalize(a):
    length = mag(a)
    if length <= 0:
        raise ValueError("Cannot normalize zero vector")
    return a.scale(1.0 / length)


def radial_distance(point, origin, axis):
    rel = point - origin
    axial = axis.scale(dot(rel, axis))
    radial = rel - axial
    return mag(radial)


def exact_key(point, scale=1.0e12):
    return (round(point.x * scale), round(point.y * scale), round(point.z * scale))


def nearest_mode(target, exact_index, kd_tree):
    exact = exact_index.get(exact_key(target))
    if exact is not None:
        return exact, 0.0

    best, best_distance2 = nearest_in_kd_tree(target, kd_tree, None, float("inf"))
    if best is None:
        raise ValueError("Cannot map to an empty FEM mode")
    return best, math.sqrt(best_distance2)


def write_sample_fem(path, patches, origin, axis):
    all_points = [point for points in patches.values() for point in points]
    radii = [radial_distance(point, origin, axis) for point in all_points]
    r_min = min(radii)
    r_max = max(radii)
    span = max(r_max - r_min, 1.0e-12)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"])

        node_i = 0
        for patch_name, points in sorted(patches.items()):
            for point in points:
                s = (radial_distance(point, origin, axis) - r_min) / span
                shape = s * s * (3.0 - 2.0 * s)
                writer.writerow(
                    [
                        "{}_{}".format(patch_name, node_i),
                        "{:.12g}".format(point.x),
                        "{:.12g}".format(point.y),
                        "{:.12g}".format(point.z),
                        "0",
                        "{:.12g}".format(shape),
                        "0",
                    ]
                )
                node_i += 1


def map_fem_to_patches(fem_nodes, patches, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    exact_index = {exact_key(node.point): node for node in fem_nodes}
    kd_tree = build_kd_tree(fem_nodes)
    max_distance = 0.0
    row_count = 0

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "patchName",
                "patchPointI",
                "x",
                "y",
                "z",
                "phi_x",
                "phi_y",
                "phi_z",
                "sourceNodeId",
                "sourceDistance",
            ]
        )

        for patch_name, points in sorted(patches.items()):
            for i, point in enumerate(points):
                node, distance = nearest_mode(point, exact_index, kd_tree)
                max_distance = max(max_distance, distance)
                row_count += 1
                writer.writerow(
                    [
                        patch_name,
                        i,
                        "{:.12g}".format(point.x),
                        "{:.12g}".format(point.y),
                        "{:.12g}".format(point.z),
                        "{:.12g}".format(node.phi.x),
                        "{:.12g}".format(node.phi.y),
                        "{:.12g}".format(node.phi.z),
                        node.node_id,
                        "{:.12g}".format(distance),
                    ]
                )

    print("Mapped {} patch points across {} patches -> {}".format(row_count, len(patches), output))
    print("Maximum nearest-node distance: {:.6g}".format(max_distance))


def parse_vector(text):
    values = [float(value) for value in text.strip("()").replace(",", " ").split()]
    if len(values) != 3:
        raise ValueError("Expected three vector components, got {!r}".format(text))
    return Point(values[0], values[1], values[2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path, help="OpenFOAM case directory")
    parser.add_argument("--patch-regex", default="propeller.*", help="Patch regex to map")
    parser.add_argument("--fem", required=True, type=Path, help="Input FEM mode CSV")
    parser.add_argument("--out", required=True, type=Path, help="Output mapped mode CSV")
    parser.add_argument(
        "--make-sample-fem",
        action="store_true",
        help="Create a synthetic propeller mode on the selected patches before mapping",
    )
    parser.add_argument("--origin", default="(0 0 0)", help="Rotation origin for sample mode")
    parser.add_argument("--axis", default="(0 1 0)", help="Rotation axis for sample mode")
    args = parser.parse_args()

    patches = patch_points(args.case, args.patch_regex)
    origin = parse_vector(args.origin)
    axis = normalize(parse_vector(args.axis))

    if args.make_sample_fem:
        write_sample_fem(args.fem, patches, origin, axis)
        print("Wrote sample FEM mode -> {}".format(args.fem))

    fem_nodes = read_fem_csv(args.fem)
    map_fem_to_patches(fem_nodes, patches, args.out)


if __name__ == "__main__":
    main()
