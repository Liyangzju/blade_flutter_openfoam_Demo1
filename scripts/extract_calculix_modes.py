#!/usr/bin/env python3
"""Extract CalculiX modal displacements to OpenFOAM Demo2 FEM-mode CSV files.

Input:
    wing_shell_modal.dat
    wing_shell_nodes.csv

Output:
    mode_01.csv, mode_02.csv, ...
    mode_frequencies.csv

Each mode CSV has the format expected by map_fem_mode_to_patch.py:

    nodeId,x,y,z,phi_x,phi_y,phi_z
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path


FLOAT_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"


@dataclass(frozen=True)
class Node:
    node_id: int
    x: float
    y: float
    z: float


def parse_float(text: str) -> float:
    return float(text.replace("D", "E").replace("d", "e"))


def read_node_map(path: Path) -> dict[int, Node]:
    nodes: dict[int, Node] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"ccxNodeId", "x", "y", "z"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")

        for row in reader:
            node_id = int(row["ccxNodeId"])
            nodes[node_id] = Node(
                node_id=node_id,
                x=float(row["x"]),
                y=float(row["y"]),
                z=float(row["z"]),
            )

    if not nodes:
        raise ValueError(f"No nodes found in {path}")

    return nodes


def parse_frequencies(lines: list[str]) -> dict[int, float]:
    frequencies: dict[int, float] = {}
    row_pattern = re.compile(
        rf"^\s*(\d+)\s+({FLOAT_RE})\s+({FLOAT_RE})\s+({FLOAT_RE})\s+({FLOAT_RE})\s*$"
    )

    in_table = False
    for line in lines:
        if "E I G E N V A L U E   O U T P U T" in line:
            in_table = True
            continue
        if in_table and "P A R T I C I P A T I O N" in line:
            break
        if not in_table:
            continue

        match = row_pattern.match(line)
        if match:
            mode_id = int(match.group(1))
            frequency_hz = parse_float(match.group(4))
            frequencies[mode_id] = frequency_hz

    return frequencies


def parse_displacements(lines: list[str]) -> dict[int, dict[int, tuple[float, float, float]]]:
    modes: dict[int, dict[int, tuple[float, float, float]]] = {}
    mode_pattern = re.compile(r"E I G E N V A L U E\s+N U M B E R\s+(\d+)")
    row_pattern = re.compile(rf"^\s*(\d+)\s+({FLOAT_RE})\s+({FLOAT_RE})\s+({FLOAT_RE})\s*$")

    current_mode: int | None = None
    reading_rows = False
    saw_row = False

    for line in lines:
        mode_match = mode_pattern.search(line)
        if mode_match:
            current_mode = int(mode_match.group(1))
            modes[current_mode] = {}
            reading_rows = False
            saw_row = False
            continue

        if current_mode is None:
            continue

        if "displacements" in line and "ALLNODES" in line:
            reading_rows = True
            saw_row = False
            continue

        if not reading_rows:
            continue

        row_match = row_pattern.match(line)
        if row_match:
            node_id = int(row_match.group(1))
            modes[current_mode][node_id] = (
                parse_float(row_match.group(2)),
                parse_float(row_match.group(3)),
                parse_float(row_match.group(4)),
            )
            saw_row = True
            continue

        if line.strip() == "" and saw_row:
            reading_rows = False

    return modes


def normalize_mode(
    values: dict[int, tuple[float, float, float]],
    mode: str,
) -> dict[int, tuple[float, float, float]]:
    if mode == "none":
        return values

    if mode != "max":
        raise ValueError(f"Unsupported normalization: {mode}")

    max_mag = max(math.sqrt(x * x + y * y + z * z) for x, y, z in values.values())
    if max_mag <= 0:
        raise ValueError("Cannot normalize mode with zero displacement magnitude")

    return {
        node_id: (x / max_mag, y / max_mag, z / max_mag)
        for node_id, (x, y, z) in values.items()
    }


def write_mode_csv(
    path: Path,
    nodes: dict[int, Node],
    values: dict[int, tuple[float, float, float]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    missing = sorted(set(nodes).difference(values))
    if missing:
        sample = ", ".join(str(node_id) for node_id in missing[:10])
        raise ValueError(f"Mode displacement is missing {len(missing)} nodes, first: {sample}")

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"])
        for node_id in sorted(nodes):
            node = nodes[node_id]
            ux, uy, uz = values[node_id]
            writer.writerow(
                [
                    node_id,
                    f"{node.x:.12g}",
                    f"{node.y:.12g}",
                    f"{node.z:.12g}",
                    f"{ux:.12g}",
                    f"{uy:.12g}",
                    f"{uz:.12g}",
                ]
            )


def write_frequency_csv(path: Path, frequencies: dict[int, float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", "frequency_Hz"])
        for mode_id in sorted(frequencies):
            writer.writerow([mode_id, f"{frequencies[mode_id]:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", required=True, type=Path, help="CalculiX .dat file")
    parser.add_argument("--node-map", required=True, type=Path, help="Node map CSV")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output mode CSV directory")
    parser.add_argument(
        "--normalize",
        choices=["max", "none"],
        default="max",
        help="Normalize each mode shape. max gives dimensionless phi with max |phi| = 1.",
    )
    args = parser.parse_args()

    lines = args.dat.read_text(encoding="utf-8", errors="ignore").splitlines()
    nodes = read_node_map(args.node_map)
    frequencies = parse_frequencies(lines)
    modes = parse_displacements(lines)

    if not modes:
        raise ValueError(f"No modal displacement blocks found in {args.dat}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_frequency_csv(args.out_dir / "mode_frequencies.csv", frequencies)

    for mode_id in sorted(modes):
        values = normalize_mode(modes[mode_id], args.normalize)
        write_mode_csv(args.out_dir / f"mode_{mode_id:02d}.csv", nodes, values)

    print(f"Extracted {len(modes)} modes -> {args.out_dir}")
    if frequencies:
        for mode_id in sorted(frequencies):
            print(f"mode {mode_id}: {frequencies[mode_id]:.6g} Hz")


if __name__ == "__main__":
    main()
