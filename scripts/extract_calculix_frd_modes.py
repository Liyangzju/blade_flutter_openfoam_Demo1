#!/usr/bin/env python3
"""Extract modal displacement vectors from a CalculiX FRD file.

Input:
    Analysis-1.frd

Output:
    mode_frequencies.csv
    mode_01.csv, mode_02.csv, ...

Each mode CSV has the format expected by map_fem_mode_to_patches.py:

    nodeId,x,y,z,phi_x,phi_y,phi_z

The FRD format uses fixed-width numeric fields in many places, so this parser
does not split displacement rows on whitespace. This matters when negative
values are adjacent to node ids or previous components.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Node:
    node_id: int
    x: float
    y: float
    z: float


Vector = tuple[float, float, float]


def parse_float(text: str) -> float:
    return float(text.strip().replace("D", "E").replace("d", "e"))


def parse_vector_row(line: str) -> tuple[int, Vector]:
    """Parse an FRD row containing one node id followed by three vectors."""
    node_id = int(line[3:13])
    return (
        node_id,
        (
            parse_float(line[13:25]),
            parse_float(line[25:37]),
            parse_float(line[37:49]),
        ),
    )


def parse_modes_arg(text: str | None) -> set[int] | None:
    if not text:
        return None

    modes: set[int] = set()
    for item in text.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        modes.add(int(item))

    if not modes:
        return None
    return modes


def c3d10_surface_face_nodes(connectivity: list[int]) -> list[tuple[tuple[int, int, int], tuple[int, ...]]]:
    """Return C3D10 faces keyed by their three corner nodes.

    CalculiX/Abaqus C3D10 node order:
        1-4 are corners,
        5: 1-2, 6: 2-3, 7: 3-1,
        8: 1-4, 9: 2-4, 10: 3-4.
    """
    if len(connectivity) < 10:
        raise ValueError("C3D10 element requires 10 node ids")

    n = connectivity
    faces = [
        (n[0], n[1], n[2], n[4], n[5], n[6]),
        (n[0], n[3], n[1], n[7], n[8], n[4]),
        (n[1], n[3], n[2], n[8], n[9], n[5]),
        (n[2], n[3], n[0], n[9], n[7], n[6]),
    ]
    return [(tuple(sorted(face[:3])), face) for face in faces]


def c3d10_faces_by_name(connectivity: list[int]) -> dict[str, tuple[int, ...]]:
    if len(connectivity) < 10:
        raise ValueError("C3D10 element requires 10 node ids")

    n = connectivity
    return {
        "S1": (n[0], n[1], n[2], n[4], n[5], n[6]),
        "S2": (n[0], n[3], n[1], n[7], n[8], n[4]),
        "S3": (n[1], n[3], n[2], n[8], n[9], n[5]),
        "S4": (n[2], n[3], n[0], n[9], n[7], n[6]),
    }


def parse_keyword(line: str) -> tuple[str, dict[str, str], set[str]]:
    parts = [part.strip() for part in line.strip()[1:].split(",")]
    keyword = parts[0].upper()
    params: dict[str, str] = {}
    flags: set[str] = set()

    for part in parts[1:]:
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            params[key.strip().upper()] = value.strip()
        else:
            flags.add(part.strip().upper())

    return keyword, params, flags


def parse_int_tokens(line: str) -> list[int]:
    values: list[int] = []
    for token in line.replace(",", " ").split():
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def expand_generate(values: list[int]) -> list[int]:
    expanded: list[int] = []
    if len(values) % 3:
        raise ValueError("Generated set entries must be start,end,step triples")

    for start, end, step in zip(values[0::3], values[1::3], values[2::3]):
        if step == 0:
            raise ValueError("Generated set step cannot be zero")
        expanded.extend(range(start, end + (1 if step > 0 else -1), step))

    return expanded


def read_inp_node_selection(
    inp_path: Path,
    surface_regex: str | None,
    nset_regex: str | None,
) -> tuple[set[int], list[str]]:
    """Read named node selections from a CalculiX/PrePoMax input file."""
    surface_pattern = re.compile(surface_regex) if surface_regex else None
    nset_pattern = re.compile(nset_regex) if nset_regex else None

    elements: dict[int, list[int]] = {}
    elsets: dict[str, set[int]] = {}
    nsets: dict[str, set[int]] = {}
    surfaces: dict[str, list[tuple[str, str]]] = {}

    section: str | None = None
    section_name: str | None = None
    section_generate = False
    element_elset: str | None = None

    with inp_path.open(encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("**"):
                continue

            if line.startswith("*"):
                keyword, params, flags = parse_keyword(line)
                section = None
                section_name = None
                section_generate = "GENERATE" in flags
                element_elset = None

                if keyword == "ELEMENT":
                    section = "element"
                    element_elset = params.get("ELSET")
                    if element_elset:
                        elsets.setdefault(element_elset, set())
                elif keyword == "ELSET":
                    section = "elset"
                    section_name = params.get("ELSET")
                    if section_name:
                        elsets.setdefault(section_name, set())
                elif keyword == "NSET":
                    section = "nset"
                    section_name = params.get("NSET")
                    if section_name:
                        nsets.setdefault(section_name, set())
                elif keyword == "SURFACE":
                    section = "surface"
                    section_name = params.get("NAME")
                    if section_name:
                        surfaces.setdefault(section_name, [])
                continue

            if section == "element":
                values = parse_int_tokens(line)
                if len(values) >= 2:
                    element_id = values[0]
                    elements[element_id] = values[1:]
                    if element_elset:
                        elsets[element_elset].add(element_id)
                continue

            if section == "elset" and section_name:
                values = parse_int_tokens(line)
                if section_generate and values:
                    values = expand_generate(values)
                elsets[section_name].update(values)
                continue

            if section == "nset" and section_name:
                values = parse_int_tokens(line)
                if section_generate and values:
                    values = expand_generate(values)
                nsets[section_name].update(values)
                continue

            if section == "surface" and section_name:
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 2:
                    surfaces[section_name].append((parts[0], parts[1].upper()))

    selected_nodes: set[int] = set()
    selected_names: list[str] = []

    if nset_pattern:
        for name, node_ids in sorted(nsets.items()):
            if nset_pattern.fullmatch(name):
                selected_nodes.update(node_ids)
                selected_names.append(f"NSET:{name}")

    if surface_pattern:
        for name, refs in sorted(surfaces.items()):
            if not surface_pattern.fullmatch(name):
                continue

            selected_names.append(f"SURFACE:{name}")
            for elset_name, face_name in refs:
                element_ids = elsets.get(elset_name)
                if element_ids is None:
                    raise ValueError(f"Surface {name} references missing elset {elset_name}")

                for element_id in element_ids:
                    connectivity = elements.get(element_id)
                    if connectivity is None:
                        raise ValueError(f"Surface {name} references missing element {element_id}")

                    faces = c3d10_faces_by_name(connectivity)
                    if face_name not in faces:
                        raise ValueError(f"Unsupported C3D10 face {face_name!r} in surface {name}")
                    selected_nodes.update(faces[face_name])

    if not selected_nodes:
        selectors = []
        if surface_regex:
            selectors.append(f"surface_regex={surface_regex!r}")
        if nset_regex:
            selectors.append(f"nset_regex={nset_regex!r}")
        raise ValueError(f"No nodes matched {', '.join(selectors)} in {inp_path}")

    return selected_nodes, selected_names


def add_element_faces(
    element_type: int,
    connectivity: list[int],
    face_counts: dict[tuple[int, int, int], int],
    face_nodes: dict[tuple[int, int, int], tuple[int, ...]],
) -> None:
    # FRD type 6 is the C3D10 tetrahedron used by the current PrePoMax model.
    if element_type != 6:
        return

    for key, face in c3d10_surface_face_nodes(connectivity):
        face_counts[key] = face_counts.get(key, 0) + 1
        face_nodes.setdefault(key, face)


def surface_node_set(
    face_counts: dict[tuple[int, int, int], int],
    face_nodes: dict[tuple[int, int, int], tuple[int, ...]],
) -> set[int]:
    nodes: set[int] = set()
    for key, count in face_counts.items():
        if count == 1:
            nodes.update(face_nodes[key])
    return nodes


def normalize_values(values: dict[int, Vector], mode: str) -> dict[int, Vector]:
    if mode == "none":
        return values

    if mode != "max":
        raise ValueError(f"Unsupported normalization mode: {mode}")

    max_mag = max(math.sqrt(x * x + y * y + z * z) for x, y, z in values.values())
    if max_mag <= 0:
        raise ValueError("Cannot normalize a mode with zero displacement magnitude")

    return {
        node_id: (x / max_mag, y / max_mag, z / max_mag)
        for node_id, (x, y, z) in values.items()
    }


def write_mode_csv(
    path: Path,
    nodes: dict[int, Node],
    values: dict[int, Vector],
    normalization: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = normalize_values(values, normalization)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["nodeId", "x", "y", "z", "phi_x", "phi_y", "phi_z"])
        for node_id in sorted(values):
            node = nodes[node_id]
            phi = values[node_id]
            writer.writerow(
                [
                    node_id,
                    f"{node.x:.12g}",
                    f"{node.y:.12g}",
                    f"{node.z:.12g}",
                    f"{phi[0]:.12g}",
                    f"{phi[1]:.12g}",
                    f"{phi[2]:.12g}",
                ]
            )


def write_frequency_csv(path: Path, frequencies: dict[int, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", "frequency_Hz"])
        for mode_id in sorted(frequencies):
            writer.writerow([mode_id, f"{frequencies[mode_id]:.12g}"])


def extract_frd_modes(
    frd_path: Path,
    out_dir: Path,
    normalization: str,
    selected_modes: set[int] | None,
    surface_only: bool,
    inp_path: Path | None,
    surface_regex: str | None,
    nset_regex: str | None,
) -> None:
    nodes: dict[int, Node] = {}
    frequencies: dict[int, float] = {}

    face_counts: dict[tuple[int, int, int], int] = {}
    face_nodes: dict[tuple[int, int, int], tuple[int, ...]] = {}
    selected_node_ids: set[int] | None = None
    selected_names: list[str] = []

    if inp_path and (surface_regex or nset_regex):
        selected_node_ids, selected_names = read_inp_node_selection(
            inp_path=inp_path,
            surface_regex=surface_regex,
            nset_regex=nset_regex,
        )

    reading_nodes = False
    reading_elements = False
    reading_disp = False
    current_element_type: int | None = None
    current_mode: int | None = None
    current_frequency: float | None = None
    current_values: dict[int, Vector] = {}

    def wanted_mode(mode_id: int | None) -> bool:
        return mode_id is not None and (selected_modes is None or mode_id in selected_modes)

    def ensure_surface_nodes() -> set[int] | None:
        nonlocal selected_node_ids
        if selected_node_ids is not None:
            return selected_node_ids
        if not surface_only:
            return None
        if selected_node_ids is None:
            selected_node_ids = surface_node_set(face_counts, face_nodes)
            if not selected_node_ids:
                raise ValueError("Could not identify any exterior C3D10 surface nodes in the FRD file")
        return selected_node_ids

    def finish_disp_block() -> None:
        nonlocal reading_disp, current_values
        if not reading_disp:
            return
        if current_mode is None:
            raise ValueError("DISP block ended without a PMODE header")
        if current_values:
            write_mode_csv(
                out_dir / f"mode_{current_mode:02d}.csv",
                nodes,
                current_values,
                normalization,
            )
            if current_frequency is not None:
                frequencies[current_mode] = current_frequency
            print(
                f"Wrote mode_{current_mode:02d}.csv "
                f"({len(current_values)} nodes, frequency={current_frequency:g} Hz)"
            )
        current_values = {}
        reading_disp = False

    with frd_path.open(encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("2C"):
                reading_nodes = True
                continue

            if stripped.startswith("3C"):
                reading_elements = True
                continue

            if reading_nodes:
                if stripped == "-3":
                    reading_nodes = False
                    continue
                if line.startswith(" -1"):
                    node_id, coords = parse_vector_row(line)
                    nodes[node_id] = Node(node_id, *coords)
                continue

            if reading_elements:
                if stripped == "-3":
                    reading_elements = False
                    continue
                if line.startswith(" -1"):
                    fields = line.split()
                    current_element_type = int(fields[2]) if len(fields) > 2 else None
                    continue
                if line.startswith(" -2") and current_element_type is not None:
                    connectivity = [int(value) for value in line.split()[1:]]
                    add_element_faces(current_element_type, connectivity, face_counts, face_nodes)
                continue

            if stripped.startswith("1PMODE"):
                fields = stripped.split()
                current_mode = int(fields[-1])
                continue

            if stripped.startswith("100CL"):
                fields = stripped.split()
                if len(fields) >= 4:
                    current_frequency = parse_float(fields[2])
                continue

            if line.startswith(" -4"):
                finish_disp_block()
                fields = line.split()
                field_name = fields[1] if len(fields) > 1 else ""
                if field_name == "DISP" and wanted_mode(current_mode):
                    ensure_surface_nodes()
                    reading_disp = True
                    current_values = {}
                continue

            if reading_disp:
                if stripped == "-3":
                    finish_disp_block()
                    continue
                if line.startswith(" -5"):
                    continue
                if line.startswith(" -1"):
                    node_id, phi = parse_vector_row(line)
                    if selected_node_ids is None or node_id in selected_node_ids:
                        if node_id not in nodes:
                            raise ValueError(f"Mode references node {node_id}, but no coordinates were read")
                        current_values[node_id] = phi

    finish_disp_block()
    write_frequency_csv(out_dir / "mode_frequencies.csv", frequencies)

    if not frequencies:
        raise ValueError(f"No modal displacement blocks found in {frd_path}")

    print(f"Wrote frequencies -> {out_dir / 'mode_frequencies.csv'}")
    print(f"Read {len(nodes)} FRD nodes from {frd_path}")
    if selected_names:
        print(f"Used {len(selected_node_ids or [])} named INP nodes from: {', '.join(selected_names)}")
    elif surface_only and selected_node_ids is not None:
        print(f"Used {len(selected_node_ids)} exterior surface nodes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frd", required=True, type=Path, help="CalculiX FRD result file")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output mode CSV directory")
    parser.add_argument(
        "--normalize",
        choices=["max", "none"],
        default="max",
        help="Normalize each mode by maximum displacement magnitude.",
    )
    parser.add_argument(
        "--modes",
        help="Optional comma-separated mode list to extract, for example: 1,7,10",
    )
    parser.add_argument(
        "--surface-only",
        action="store_true",
        help="Use only exterior C3D10 surface nodes for mapping to CFD surfaces.",
    )
    parser.add_argument(
        "--inp",
        type=Path,
        help="Optional CalculiX input file containing named PrePoMax surfaces or node sets.",
    )
    parser.add_argument(
        "--surface-regex",
        help="Only extract nodes from named *Surface entries matching this full regex, for example: blade.*",
    )
    parser.add_argument(
        "--nset-regex",
        help="Only extract nodes from named *Nset entries matching this full regex.",
    )
    args = parser.parse_args()

    extract_frd_modes(
        frd_path=args.frd,
        out_dir=args.out_dir,
        normalization=args.normalize,
        selected_modes=parse_modes_arg(args.modes),
        surface_only=args.surface_only,
        inp_path=args.inp,
        surface_regex=args.surface_regex,
        nset_regex=args.nset_regex,
    )


if __name__ == "__main__":
    main()
