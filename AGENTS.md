# Codex Project Notes

This repository is the local OpenFOAM v2112 blade-flutter workspace reconstructed from the archived Codex session:

```text
/home/liyang/.codex/archived_sessions/rollout-2026-05-13T19-53-21-019e212f-305d-7731-a29f-88998d421087.jsonl
```

Use this file as the persistent project memory for future Codex work.

## Project Root

```text
/home/liyang/OpenFOAM/liyang-v2112/run/wingMotion
```

Recommended OpenFOAM environment:

```bash
source /home/liyang/openFoam/OpenFOAM-v2112/etc/bashrc
```

## Active Direction

The project starts from the official OpenFOAM `wingMotion` tutorial and develops it toward blade flutter analysis:

1. Demo1: 2D airfoil prescribed analytical modal vibration.
2. Demo2: CalculiX shell modal analysis, mode extraction, and OpenFOAM mapped modal motion.
3. Demo3: six-blade rotating propeller case with CalculiX modal extraction, FEM-to-CFD mode mapping, blade-wise phase control, and OpenFOAM transient motion.

The current active Demo3 case is:

```text
demo3/
```

The older propeller prototype may exist locally for reference only:

```text
demo3/propeller.org/
```

Do not treat `demo3/propeller.org/` as the active case unless the user explicitly asks.

## Current Demo3 Model

Important current assumptions:

- Blade patches are named `blade1` through `blade6`.
- Root/hub patch is named `hub`.
- Rotor axis is `(0 0 1)`.
- Rotor cellZone is `rotter.SLDPRT.rotor`.
- Dynamic mesh solver is `solidBodyDisplacementLaplacian`.
- The rigid rotation comes from `constant/dynamicMeshDict`.
- The modal deformation comes from `0/pointDisplacement`.
- Modal parameters live in `constant/modeShapes/modeProperties`.
- The mapped mode file is `constant/modeShapes/bladeMode1_mapped.csv`.
- `ibpa` in `modeProperties` is the inter-blade phase angle in radians.

The intended Demo3 `Allrun` chain is:

```text
foamFormatConvert
-> extract PrePoMax/CalculiX FRD modes to CSV
-> copy the first positive modal frequency into modeProperties
-> select MODE/SELECT_MODE, or use the first positive-frequency mode
-> map the selected FEM mode CSV back to blade.* patches
-> decomposePar
-> pimpleFoam in parallel
-> reconstructPar
```

## PrePoMax / CalculiX Source

Demo3 no longer builds a provisional CalculiX shell model from the CFD patch points.
It now expects a proper structural model prepared in PrePoMax and solved by CalculiX.

Expected local input files:

```text
demo3/fem/prepomax/Analysis-1.inp
demo3/fem/prepomax/Analysis-1.frd
```

`Analysis-1.inp` should contain named PrePoMax surfaces such as:

```text
blade1
blade2
blade3
blade4
blade5
blade6
hub
```

`demo3/Allrun` extracts only the FEM nodes that belong to surfaces matching
`FEM_SURFACE_REGEX`, which defaults to `blade.*`. This avoids mapping hub nodes
into the OpenFOAM blade patch motion.

Useful run examples:

```bash
cd /home/liyang/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./Allrun
EXTRACT_MODES=10 MODE=10 ./Allrun
FEM_SURFACE_REGEX='blade.*' MODE=10 ./Allrun
```

## Generated Files

Do not commit OpenFOAM/CalculiX generated output unless the user asks. The repository intentionally ignores:

- time directories;
- `processor*/`;
- `postProcessing/`;
- `dynamicCode/`;
- generated `constant/polyMesh/`;
- CalculiX result files such as `.dat`, `.frd`, `.sta`;
- generated Demo3 FEM and mapped mode CSV output.

## Useful Checks

Lightweight checks that are safe before larger runs:

```bash
bash -n demo3/Allrun
bash -n demo3/Allclean
bash -n demo3/AllviewFem
python3 -m py_compile scripts/extract_calculix_frd_modes.py scripts/map_fem_mode_to_patches.py scripts/export_mapped_mode_to_vtk.py
foamDictionary demo3/constant/dynamicMeshDict
foamDictionary demo3/0/pointDisplacement
foamDictionary demo3/constant/modeShapes/modeProperties
foamDictionary demo3/system/fvSolution
```

Full Demo3 run:

```bash
cd /home/liyang/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./Allrun
```

This may be expensive because it extracts modes and runs a parallel OpenFOAM transient case.

Known validation status:

- `bash -n demo3/Allrun`, `bash -n demo3/Allclean`, and `bash -n demo3/AllviewFem` pass.
- The FRD extraction path reads PrePoMax/CalculiX modal displacement blocks and named INP surfaces.
- With named `blade1` through `blade6` surfaces, extraction keeps only blade surface nodes.
- The mapping script uses a KD-tree fallback for nearest FEM node lookup, which is needed for large structural meshes.
- `AllviewFem` can export mapped modes to VTK for ParaView checks, for example `MODE=10 SCALE=0.05 ./AllviewFem`.

## Git Caution

The worktree may contain user edits and generated state. Never revert files or remove generated folders unless the user asks. If `git push` says `Everything up-to-date`, still check `git status`; uncommitted local changes are not pushed.
