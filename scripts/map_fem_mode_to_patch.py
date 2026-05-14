#!/usr/bin/env python3
"""Map FEM surface mode data to an OpenFOAM patch.

Input FEM CSV columns:
    nodeId,x,y,z,phi_x,phi_y,phi_z

Output mapped CSV columns:
    patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance

The output can be read by the Demo2 codedFixedValue boundary condition.
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


@dataclass(frozen=True)
class FemNode:
    node_id: str
    point: Point
    phi: Point


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


def patch_points(case_dir: Path, patch_name: str) -> list[Point]:
    poly_mesh = case_dir / "constant" / "polyMesh"
    points = read_points(poly_mesh / "points")
    faces = read_faces(poly_mesh / "faces")
    n_faces, start_face = read_patch_info(poly_mesh / "boundary", patch_name)

    point_labels: list[int] = []
    seen: set[int] = set()

    for face in faces[start_face : start_face + n_faces]:
        for point_label in face:
            if point_label not in seen:
                seen.add(point_label)
                point_labels.append(point_label)

    return [points[label] for label in point_labels]


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


def distance2(a: Point, b: Point) -> float:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2


def nearest_mode(target: Point, nodes: list[FemNode]) -> tuple[FemNode, float]:
    best = min(nodes, key=lambda node: distance2(target, node.point))
    return best, math.sqrt(distance2(target, best.point))


def write_sample_fem(path: Path, targets: list[Point], x_le: float, chord: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"])
        for i, point in enumerate(targets):
            xi = min(max((point.x - x_le) / chord, 0.0), 1.0)
            phi_y = math.sin(math.pi * xi)
            writer.writerow(
                [
                    i,
                    f"{point.x:.12g}",
                    f"{point.y:.12g}",
                    f"{point.z:.12g}",
                    "0",
                    f"{phi_y:.12g}",
                    "0",
                ]
            )


def map_fem_to_patch(fem_nodes: list[FemNode], targets: list[Point], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    max_distance = 0.0

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
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

        for i, point in enumerate(targets):
            node, distance = nearest_mode(point, fem_nodes)
            max_distance = max(max_distance, distance)
            writer.writerow(
                [
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

    print(f"Mapped {len(targets)} patch points -> {output}")
    print(f"Maximum nearest-node distance: {max_distance:.6g}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path, help="OpenFOAM case directory")
    parser.add_argument("--patch", default="wing", help="Patch name to map")
    parser.add_argument("--fem", required=True, type=Path, help="Input FEM mode CSV")
    parser.add_argument("--out", required=True, type=Path, help="Output mapped mode CSV")
    parser.add_argument(
        "--make-sample-fem",
        action="store_true",
        help="Create a synthetic FEM CSV on the patch before mapping",
    )
    parser.add_argument("--x-leading-edge", default=0.0, type=float)
    parser.add_argument("--chord", default=1.0, type=float)
    args = parser.parse_args()

    targets = patch_points(args.case, args.patch)

    if args.make_sample_fem:
        write_sample_fem(args.fem, targets, args.x_leading_edge, args.chord)
        print(f"Wrote sample FEM mode -> {args.fem}")

    fem_nodes = read_fem_csv(args.fem)
    map_fem_to_patch(fem_nodes, targets, args.out)


if __name__ == "__main__":
    main()
