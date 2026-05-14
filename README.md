# wingMotion Blade Flutter Demo

OpenFOAM v2112 development workspace for blade flutter experiments.

Current focus:

- Demo 1: 2D airfoil prescribed modal vibration
- OpenFOAM case: `wingMotion2D_pimpleFoam`
- Technical note: `docs/demo1二维自定义振动.md`

The repository should track source case setup and documentation, not solver output.

Tracked content should include:

- `Allrun`, `Allclean`, helper scripts
- `docs/`
- case `0/`, `constant/`, `system/` dictionaries
- future `scripts/`, `src/`, `cases/`

Ignored content includes:

- time directories such as `0.01/`, `1/`, `1000/`
- `processor*/`
- `postProcessing/`
- `dynamicCode/`
- generated `constant/polyMesh/`
- logs and visualization output

## Git Setup

After installing Git:

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion
git init
git add .gitignore README.md docs Allrun Allclean openParaFoam.sh \
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
