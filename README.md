# wingMotion Blade Flutter Demo

OpenFOAM v2112 development workspace for blade flutter experiments.

Current focus:

- Demo 1: 2D airfoil prescribed modal vibration
- Demo 2: CalculiX FEM modal analysis and mapped modal vibration
- Demo 3: six-blade rotating propeller workflow driven by PrePoMax/CalculiX modal results
- OpenFOAM case: `wingMotion2D_pimpleFoam`
- Project memory for Codex: `AGENTS.md`
- Project overview: `docs/项目总览_叶片颤振.md`
- Technical note: `docs/demo1二维自定义振动.md`
- Technical note: `docs/demo2_FEM模态导入.md`
- Technical note: `docs/demo3_三维旋转叶片FEM模态颤振.md`

The repository should track source case setup and documentation, not solver output.

Tracked content should include:

- `Allrun`, `Allclean`, helper scripts
- `docs/`
- case `0/`, `constant/`, `system/` dictionaries
- future `scripts/`, `src/`, `cases/`
- `demo2/demo2A/` CalculiX FEM setup and extracted surface mode CSV files
- `demo2/demo2B/` OpenFOAM case and mapped mode CSV files
- `demo3/` active six-blade rotating modal-motion case setup

Ignored content includes:

- time directories such as `0.01/`, `1/`, `1000/`
- `processor*/`
- `postProcessing/`
- `dynamicCode/`
- generated `constant/polyMesh/`, except the small tracked Demo2B reference mesh
- logs and visualization output

## Git Setup

After installing Git:

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion
git init
git add .gitignore README.md AGENTS.md docs Allrun Allclean openParaFoam.sh \
    wingMotion2D_pimpleFoam/0 \
    wingMotion2D_pimpleFoam/constant \
    wingMotion2D_pimpleFoam/system \
    wingMotion2D_simpleFoam/0 \
    wingMotion2D_simpleFoam/constant \
    wingMotion2D_simpleFoam/system \
    wingMotion_snappyHexMesh/constant \
    wingMotion_snappyHexMesh/system
git commit -m "Initial blade flutter demo workspace"
```

Then add your remote repository:

```bash
git remote add origin <your-remote-url>
git branch -M main
git push -u origin main
```
