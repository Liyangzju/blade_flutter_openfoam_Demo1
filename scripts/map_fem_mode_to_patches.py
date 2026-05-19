#!/usr/bin/env python3
"""Map FEM surface mode data to one or more OpenFOAM patches.

Input FEM CSV columns:
    nodeId,x,y,z,phi_x,phi_y,phi_z

Output mapped CSV columns:
    patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance

The Demo3 propeller pointDisplacement boundary condition reads this mapped
format and selects rows by the current patch name.
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

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def scale(self, value: float) -> "Point":
        return Point(self.x * value, self.y * value, self.z * value)


@dataclass(frozen=True)
class FemNode:
    node_id: str
    point: Point
    phi: Point


@dataclass(frozen=True)
class KdNode:
    item: FemNode
    axis: int
    left: "KdNode | None"
    right: "KdNode | None"


@dataclass(frozen=True)
class PatchInfo:
    name: str
    n_faces: int
    start_face: int


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


def read_boundary(boundary_file: Path) -> list[PatchInfo]:
    lines = boundary_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    patches: list[PatchInfo] = []

    i = 0
    while i < len(lines):
        name = lines[i].strip()
        if not name or name.startswith("/") or name in {"(", ")"}:
            i += 1
            continue

        if i + 1 >= len(lines) or lines[i + 1].strip() != "{":
            i += 1
            continue

        block_lines: list[str] = []
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


def patch_points(case_dir: Path, patch_pattern: str) -> dict[str, list[Point]]:
    poly_mesh = case_dir / "constant" / "polyMesh"
    points = read_points(poly_mesh / "points")
    faces = read_faces(poly_mesh / "faces")
    patches = read_boundary(poly_mesh / "boundary")
    pattern = re.compile(patch_pattern)

    selected: dict[str, list[Point]] = {}
    for patch in patches:
        if not pattern.fullmatch(patch.name):
            continue

        point_labels: list[int] = []
        seen: set[int] = set()

        for face in faces[patch.start_face : patch.start_face + patch.n_faces]:
            for point_label in face:
                if point_label not in seen:
                    seen.add(point_label)
                    point_labels.append(point_label)

        selected[patch.name] = [points[label] for label in point_labels]

    if not selected:
        names = ", ".join(patch.name for patch in patches)
        raise ValueError(f"No patches matched {patch_pattern!r}. Available patches: {names}")

    return selected


def read_fem_csv(path: Path) -> list[FemNode]:
    nodes: list[FemNode] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(row for row in handle if not row.lstrip().startswith("#"))
        required = {"nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")

        for row in reader:
            nodes.append(
                FemNode(
                    node_id=row["nodeId"],
                    point=Point(float(row["x"]), float(row["y"]), float(row["z"])),
                    phi=Point(float(row["phi_x"]), float(row["phi_y"]), float(row["phi_z"])),
                )
            )

    if not nodes:
        raise ValueError(f"No FEM nodes found in {path}")

    return nodes


def dot(a: Point, b: Point) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def mag(a: Point) -> float:
    return math.sqrt(dot(a, a))


def distance2(a: Point, b: Point) -> float:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2


def coordinate(point: Point, axis: int) -> float:
    if axis == 0:
        return point.x
    if axis == 1:
        return point.y
    return point.z


def build_kd_tree(nodes: list[FemNode], depth: int = 0) -> KdNode | None:
    if not nodes:
        return None

    axis = depth % 3
    nodes = sorted(nodes, key=lambda node: coordinate(node.point, axis))
    mid = len(nodes) // 2
    return KdNode(
        item=nodes[mid],
        axis=axis,
        left=build_kd_tree(nodes[:mid], depth + 1),
        right=build_kd_tree(nodes[mid + 1 :], depth + 1),
    )


def nearest_in_kd_tree(
    target: Point,
    tree: KdNode | None,
    best: FemNode | None,
    best_distance2: float,
) -> tuple[FemNode | None, float]:
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


def normalize(a: Point) -> Point:
    length = mag(a)
    if length <= 0:
        raise ValueError("Cannot normalize zero vector")
    return a.scale(1.0 / length)


def radial_distance(point: Point, origin: Point, axis: Point) -> float:
    rel = point - origin
    axial = axis.scale(dot(rel, axis))
    radial = rel - axial
    return mag(radial)


def exact_key(point: Point, scale: float = 1.0e12) -> tuple[int, int, int]:
    return (round(point.x * scale), round(point.y * scale), round(point.z * scale))


def nearest_mode(
    target: Point,
    exact_index: dict[tuple[int, int, int], FemNode],
    kd_tree: KdNode | None,
) -> tuple[FemNode, float]:
    exact = exact_index.get(exact_key(target))
    if exact is not None:
        return exact, 0.0

    best, best_distance2 = nearest_in_kd_tree(target, kd_tree, None, math.inf)
    if best is None:
        raise ValueError("Cannot map to an empty FEM mode")
    return best, math.sqrt(best_distance2)


def write_sample_fem(
    path: Path,
    patches: dict[str, list[Point]],
    origin: Point,
    axis: Point,
) -> None:
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
                        f"{patch_name}_{node_i}",
                        f"{point.x:.12g}",
                        f"{point.y:.12g}",
                        f"{point.z:.12g}",
                        "0",
                        f"{shape:.12g}",
                        "0",
                    ]
                )
                node_i += 1


def map_fem_to_patches(
    fem_nodes: list[FemNode],
    patches: dict[str, list[Point]],
    output: Path,
) -> None:
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
                        f"{point.x:.12g}",
                        f"{point.y:.12g}",
                        f"{point.z:.12g}",
                        f"{node.phi.x:.12g}",
                        f"{node.phi.y:.12g}",
                        f"{node.phi.z:.12g}",
                        node.node_id,
                        f"{distance:.12g}",
                    ]
                )

    print(f"Mapped {row_count} patch points across {len(patches)} patches -> {output}")
    print(f"Maximum nearest-node distance: {max_distance:.6g}")


def parse_vector(text: str) -> Point:
    values = [float(value) for value in text.strip("()").replace(",", " ").split()]
    if len(values) != 3:
        raise ValueError(f"Expected three vector components, got {text!r}")
    return Point(*values)


def main() -> None:
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
        print(f"Wrote sample FEM mode -> {args.fem}")

    fem_nodes = read_fem_csv(args.fem)
    map_fem_to_patches(fem_nodes, patches, args.out)


if __name__ == "__main__":
    main()
