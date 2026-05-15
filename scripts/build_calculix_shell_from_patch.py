#!/usr/bin/env python3
"""Build a CalculiX shell modal-analysis input from an OpenFOAM patch.

This is the Demo2A bridge:

    OpenFOAM wing patch -> CalculiX shell elements -> eigenmodes

The generated CalculiX nodes are exactly the selected patch points, so the
resulting mode CSV can be mapped back to OpenFOAM with zero geometric mismatch
for this demo case.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


def _next_count(lines: list[str], start: int = 0) -> tuple[int, int]:
    for i in range(start, len(lines)):
        text = lines[i].strip()
        if text.isdigit():
            return int(text), i
    raise ValueError("Could not find OpenFOAM list count")


def read_points(points_file: Path) -> list[Point]:
    lines = points_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    n_points, count_i = _next_count(lines)

    points: list[Point] = []
    pattern = re.compile(r"\(\s*([^()\s]+)\s+([^()\s]+)\s+([^()\s]+)\s*\)")

    for line in lines[count_i + 1 :]:
        match = pattern.search(line)
        if not match:
            continue
        points.append(Point(*(float(value) for value in match.groups())))
        if len(points) == n_points:
            break

    if len(points) != n_points:
        raise ValueError(f"Expected {n_points} points, read {len(points)}")

    return points


def read_faces(faces_file: Path) -> list[list[int]]:
    lines = faces_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    n_faces, count_i = _next_count(lines)

    faces: list[list[int]] = []
    pattern = re.compile(r"\s*\d+\(([^()]*)\)")

    for line in lines[count_i + 1 :]:
        match = pattern.match(line)
        if not match:
            continue
        faces.append([int(value) for value in match.group(1).split()])
        if len(faces) == n_faces:
            break

    if len(faces) != n_faces:
        raise ValueError(f"Expected {n_faces} faces, read {len(faces)}")

    return faces


def read_patch_info(boundary_file: Path, patch_name: str) -> tuple[int, int]:
    lines = boundary_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    for i, line in enumerate(lines):
        if line.strip() != patch_name:
            continue

        block = "\n".join(lines[i : i + 20])
        n_faces = re.search(r"\bnFaces\s+(\d+)\s*;", block)
        start_face = re.search(r"\bstartFace\s+(\d+)\s*;", block)

        if not n_faces or not start_face:
            raise ValueError(f"Patch {patch_name!r} found, but nFaces/startFace missing")

        return int(n_faces.group(1)), int(start_face.group(1))

    raise ValueError(f"Patch {patch_name!r} not found in {boundary_file}")


def patch_geometry(case_dir: Path, patch_name: str) -> tuple[list[Point], list[list[int]], list[int]]:
    poly_mesh = case_dir / "constant" / "polyMesh"
    points = read_points(poly_mesh / "points")
    faces = read_faces(poly_mesh / "faces")
    n_faces, start_face = read_patch_info(poly_mesh / "boundary", patch_name)
    patch_faces = faces[start_face : start_face + n_faces]

    point_labels: list[int] = []
    seen: set[int] = set()

    for face in patch_faces:
        for point_label in face:
            if point_label not in seen:
                seen.add(point_label)
                point_labels.append(point_label)

    return points, patch_faces, point_labels


def coordinate(point: Point, axis: str) -> float:
    if axis == "x":
        return point.x
    if axis == "y":
        return point.y
    if axis == "z":
        return point.z
    raise ValueError(f"Unsupported axis {axis!r}")


def write_wrapped_ids(handle, values: list[int], per_line: int = 16) -> None:
    for start in range(0, len(values), per_line):
        chunk = values[start : start + per_line]
        handle.write(", ".join(str(value) for value in chunk))
        handle.write("\n")


def triangulate(face: list[int]) -> list[list[int]]:
    if len(face) <= 4:
        return [face]
    return [[face[0], face[i], face[i + 1]] for i in range(1, len(face) - 1)]


def write_calculix_input(
    case_dir: Path,
    patch_name: str,
    output: Path,
    node_map_output: Path,
    material_name: str,
    young: float,
    poisson: float,
    density: float,
    thickness: float,
    n_modes: int,
    root_axis: str,
    root_side: str,
    root_tol: float,
) -> None:
    points, patch_faces, point_labels = patch_geometry(case_dir, patch_name)

    foam_to_ccx = {foam_label: i + 1 for i, foam_label in enumerate(point_labels)}
    patch_points = [points[label] for label in point_labels]
    coords = [coordinate(point, root_axis) for point in patch_points]
    root_value = min(coords) if root_side == "min" else max(coords)
    span = max(coords) - min(coords)
    abs_tol = max(root_tol, 1e-12 * max(1.0, abs(span)))

    root_nodes = [
        foam_to_ccx[label]
        for label in point_labels
        if abs(coordinate(points[label], root_axis) - root_value) <= abs_tol
    ]
    if not root_nodes:
        raise ValueError("No root nodes found; increase --root-tol or check --root-axis")

    tri_elements: list[list[int]] = []
    quad_elements: list[list[int]] = []

    for face in patch_faces:
        for part in triangulate(face):
            ccx_face = [foam_to_ccx[label] for label in part]
            if len(ccx_face) == 3:
                tri_elements.append(ccx_face)
            elif len(ccx_face) == 4:
                quad_elements.append(ccx_face)
            else:
                raise ValueError(f"Unsupported face with {len(ccx_face)} points")

    output.parent.mkdir(parents=True, exist_ok=True)
    node_map_output.parent.mkdir(parents=True, exist_ok=True)

    with node_map_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ccxNodeId", "foamPointLabel", "x", "y", "z"])
        for foam_label in point_labels:
            point = points[foam_label]
            writer.writerow(
                [
                    foam_to_ccx[foam_label],
                    foam_label,
                    f"{point.x:.12g}",
                    f"{point.y:.12g}",
                    f"{point.z:.12g}",
                ]
            )

    with output.open("w", encoding="utf-8") as handle:
        handle.write("*HEADING\n")
        handle.write("Demo2A OpenFOAM patch shell modal model\n")
        handle.write("*NODE, NSET=ALLNODES\n")
        for foam_label in point_labels:
            point = points[foam_label]
            handle.write(
                f"{foam_to_ccx[foam_label]}, "
                f"{point.x:.12g}, {point.y:.12g}, {point.z:.12g}\n"
            )

        element_id = 1
        if quad_elements:
            handle.write("*ELEMENT, TYPE=S4, ELSET=WING_SHELL\n")
            for element in quad_elements:
                handle.write(f"{element_id}, " + ", ".join(str(node) for node in element) + "\n")
                element_id += 1

        if tri_elements:
            handle.write("*ELEMENT, TYPE=S3, ELSET=WING_SHELL\n")
            for element in tri_elements:
                handle.write(f"{element_id}, " + ", ".join(str(node) for node in element) + "\n")
                element_id += 1

        handle.write("*NSET, NSET=ROOT\n")
        write_wrapped_ids(handle, sorted(root_nodes))
        handle.write(f"*MATERIAL, NAME={material_name}\n")
        handle.write("*ELASTIC\n")
        handle.write(f"{young:.12g}, {poisson:.12g}\n")
        handle.write("*DENSITY\n")
        handle.write(f"{density:.12g}\n")
        handle.write(f"*SHELL SECTION, ELSET=WING_SHELL, MATERIAL={material_name}\n")
        handle.write(f"{thickness:.12g}\n")
        handle.write("*BOUNDARY\n")
        handle.write("ROOT, 1, 6, 0.0\n")
        handle.write("*STEP\n")
        handle.write("*FREQUENCY\n")
        handle.write(f"{n_modes}\n")
        handle.write("*NODE FILE\n")
        handle.write("U\n")
        handle.write("*NODE PRINT, NSET=ALLNODES\n")
        handle.write("U\n")
        handle.write("*END STEP\n")

    print(f"Wrote CalculiX input: {output}")
    print(f"Wrote node map: {node_map_output}")
    print(f"Patch points: {len(point_labels)}")
    print(f"Shell elements: {len(quad_elements) + len(tri_elements)}")
    print(f"Root nodes: {len(root_nodes)} at {root_axis}={root_value:.12g}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path, help="OpenFOAM case directory")
    parser.add_argument("--patch", default="wing", help="Patch name")
    parser.add_argument("--out", required=True, type=Path, help="Output CalculiX .inp file")
    parser.add_argument(
        "--node-map",
        required=True,
        type=Path,
        help="Output CSV mapping CalculiX nodes to OpenFOAM point labels",
    )
    parser.add_argument("--material-name", default="ALUMINUM")
    parser.add_argument("--young", default=70.0e9, type=float, help="Young's modulus")
    parser.add_argument("--poisson", default=0.33, type=float, help="Poisson ratio")
    parser.add_argument("--density", default=2700.0, type=float, help="Density")
    parser.add_argument("--thickness", default=1.0e-3, type=float, help="Shell thickness")
    parser.add_argument("--modes", default=6, type=int, help="Number of modes")
    parser.add_argument("--root-axis", choices=["x", "y", "z"], default="z")
    parser.add_argument("--root-side", choices=["min", "max"], default="min")
    parser.add_argument("--root-tol", default=1.0e-9, type=float)
    args = parser.parse_args()

    if not math.isfinite(args.young) or args.young <= 0:
        raise ValueError("--young must be positive")
    if not math.isfinite(args.density) or args.density <= 0:
        raise ValueError("--density must be positive")
    if not math.isfinite(args.thickness) or args.thickness <= 0:
        raise ValueError("--thickness must be positive")

    write_calculix_input(
        case_dir=args.case,
        patch_name=args.patch,
        output=args.out,
        node_map_output=args.node_map,
        material_name=args.material_name,
        young=args.young,
        poisson=args.poisson,
        density=args.density,
        thickness=args.thickness,
        n_modes=args.modes,
        root_axis=args.root_axis,
        root_side=args.root_side,
        root_tol=args.root_tol,
    )


if __name__ == "__main__":
    main()
