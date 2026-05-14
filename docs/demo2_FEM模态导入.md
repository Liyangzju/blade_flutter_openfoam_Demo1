# Demo 2：FEM 模态导入驱动翼型振动

## 1. 目标

Demo 2 在 Demo 1 的基础上，将解析模态：

$$
\boldsymbol{\phi}(\boldsymbol{x})
=
\begin{bmatrix}
0 \\
\sin(\pi \xi) \\
0
\end{bmatrix}
$$

替换为从 FEM 表面模态文件导入的模态向量场：

$$
\boldsymbol{\phi}_{FEM}(\boldsymbol{x})
=
\begin{bmatrix}
\phi_x(\boldsymbol{x}) \\
\phi_y(\boldsymbol{x}) \\
\phi_z(\boldsymbol{x})
\end{bmatrix}
$$

OpenFOAM 中实际施加到 `wing` patch 的位移为：

$$
\boldsymbol{u}(\boldsymbol{x},t)
=
q(t)\boldsymbol{\phi}_{FEM}(\boldsymbol{x})
$$

其中：

$$
q(t)
=
A\sin(2\pi f t+\varphi)
$$

当前 Demo2 算例路径：

```text
demo2
```

## 2. 数据流

Demo2 的数据流为：

$$
\mathrm{FEM\ surface\ mode}
\rightarrow
\mathrm{OpenFOAM\ wing\ patch}
\rightarrow
\mathrm{mapped\ mode}
\rightarrow
\mathrm{pointDisplacement}
\rightarrow
\mathrm{dynamicMesh}
$$

当前文件约定：

```text
demo2/constant/modeShapes/femMode1_sample.csv
demo2/constant/modeShapes/wingMode1_mapped.csv
```

`femMode1_sample.csv` 表示 FEM 导出的表面模态数据。

`wingMode1_mapped.csv` 表示已经映射到 OpenFOAM `wing` patch 点附近的模态数据。

## 3. FEM 输入格式

FEM 模态 CSV 采用：

```csv
nodeId,x,y,z,phi_x,phi_y,phi_z
```

其中：

$$
\boldsymbol{x}_j^{FEM}
=
\begin{bmatrix}
x_j \\
y_j \\
z_j
\end{bmatrix}
$$

$$
\boldsymbol{\phi}_j^{FEM}
=
\begin{bmatrix}
\phi_{x,j} \\
\phi_{y,j} \\
\phi_{z,j}
\end{bmatrix}
$$

单位和归一化必须在项目中固定：

$$
\boldsymbol{u}
=
q(t)\boldsymbol{\phi}
$$

如果：

$$
\max \left|\boldsymbol{\phi}\right|=1
$$

则：

$$
A
=
\max \left|\boldsymbol{u}\right|
$$

如果 FEM 输出的模态已经带长度单位，则 `amplitude` 的含义需要重新定义，避免重复放大。

## 4. 映射方法

当前脚本：

```text
scripts/map_fem_mode_to_patch.py
```

第一版采用最近邻映射：

$$
j^\*
=
\arg\min_j
\left\|
\boldsymbol{x}_i^{CFD}
-
\boldsymbol{x}_j^{FEM}
\right\|
$$

$$
\boldsymbol{\phi}_i^{CFD}
=
\boldsymbol{\phi}_{j^\*}^{FEM}
$$

映射输出：

```csv
patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance
```

其中：

$$
\mathrm{sourceDistance}_i
=
\left\|
\boldsymbol{x}_i^{CFD}
-
\boldsymbol{x}_{j^\*}^{FEM}
\right\|
$$

该值用于检查 FEM 表面节点和 OpenFOAM patch 点之间的几何匹配质量。

## 5. 当前示例数据

当前为了跑通 Demo2，先生成了一个合成 FEM 模态：

$$
\boldsymbol{\phi}_{sample}(\xi)
=
\begin{bmatrix}
0 \\
\sin(\pi\xi) \\
0
\end{bmatrix}
$$

生成并映射命令：

```bash
python3 scripts/map_fem_mode_to_patch.py \
    --case demo2 \
    --patch wing \
    --fem demo2/constant/modeShapes/femMode1_sample.csv \
    --out demo2/constant/modeShapes/wingMode1_mapped.csv \
    --make-sample-fem
```

当前验证结果：

```text
Mapped 756 patch points -> demo2/constant/modeShapes/wingMode1_mapped.csv
Maximum nearest-node distance: 0
```

真实 FEM 数据接入时，将 `--fem` 指向真实导出的 CSV，并去掉 `--make-sample-fem`：

```bash
python3 scripts/map_fem_mode_to_patch.py \
    --case demo2 \
    --patch wing \
    --fem path/to/femMode1.csv \
    --out demo2/constant/modeShapes/wingMode1_mapped.csv
```

## 6. `pointDisplacement` 实现

Demo2 中：

```text
demo2/0/pointDisplacement
```

`wing` patch 使用：

```cpp
type            codedFixedValue;
name            femModalWingDisplacement;
```

其运行时读取：

```text
constant/modeShapes/wingMode1_mapped.csv
```

每个时间步计算：

$$
\boldsymbol{d}_i(t)
=
q(t)\boldsymbol{\phi}_i
$$

代码逻辑可概括为：

$$
\left\{
\boldsymbol{x}_i^{patch}
\right\}_{i=1}^{N_p}
\rightarrow
\left\{
\boldsymbol{\phi}_i
\right\}_{i=1}^{N_p}
\rightarrow
\left\{
q(t)\boldsymbol{\phi}_i
\right\}_{i=1}^{N_p}
$$

`codedFixedValue` 中使用最近坐标匹配，而不是假设 CSV 行顺序和 `this->patch().localPoints()` 完全一致。

这使得串行和并行分块后都可以读取同一个完整 `wingMode1_mapped.csv`。

## 7. 当前振动参数

当前参数写在 `demo2/0/pointDisplacement` 中：

$$
A=0.015\ \mathrm{m}
$$

$$
f=20\ \mathrm{Hz}
$$

$$
\varphi=0
$$

角频率：

$$
\omega=2\pi f
$$

位移：

$$
\boldsymbol{u}_i(t)
=
A\sin(\omega t+\varphi)\boldsymbol{\phi}_i
$$

速度：

$$
\dot{\boldsymbol{u}}_i(t)
=
A\omega\cos(\omega t+\varphi)\boldsymbol{\phi}_i
$$

## 8. 动网格设置

Demo2 仍然使用：

```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;
motionSolverLibs (fvMotionSolvers);
motionSolver    displacementLaplacian;
diffusivity     inverseDistance 1(wing);
```

对应：

$$
\nabla \cdot
\left(
\gamma \nabla \boldsymbol{d}
\right)
=
0
$$

边界：

$$
\boldsymbol{d}\big|_{\Gamma_{wing}}
=
q(t)\boldsymbol{\phi}_{FEM}
$$

## 9. 验证记录

已在 `/tmp` 临时副本中运行一个时间步验证。

关键日志：

```text
Loaded FEM mapped mode from ".../constant/modeShapes/wingMode1_mapped.csv"
    rows: 756
    patch points: 756
    max nearest distance: 0
```

并完成：

```text
Solving for cellDisplacementy
Solving for Ux
Solving for Uy
Solving for p
End
```

说明：

$$
\mathrm{CSV}
\rightarrow
\mathrm{codedFixedValue}
\rightarrow
\mathrm{cellDisplacement}
\rightarrow
\mathrm{pimpleFoam}
$$

链路已跑通。

## 10. 后续升级

后续建议：

1. 将最近邻映射升级为反距离加权或 RBF：

$$
\boldsymbol{\phi}_i^{CFD}
=
\frac{
\sum_{j=1}^{k} w_{ij}\boldsymbol{\phi}_j^{FEM}
}{
\sum_{j=1}^{k} w_{ij}
}
$$

其中：

$$
w_{ij}
=
\frac{1}{\left(r_{ij}+\epsilon\right)^p}
$$

2. 支持多模态：

$$
\boldsymbol{u}_i(t)
=
\sum_{m=1}^{N_m}
q_m(t)\boldsymbol{\phi}_{m,i}
$$

3. 支持 IBPA：

$$
q_j(t)
=
A\sin(\omega t+j\sigma)
$$

4. 将 `codedFixedValue` 升级为正式库：

```text
src/modalMotion/modalDisplacementPointPatchVectorField
```

这样可以更干净地支持多文件、多模态、缓存、错误检查和并行运行。

## 11. 更新记录

| 日期 | 版本 | 内容 |
| --- | ---: | --- |
| 2026-05-14 | 0.1 | 建立 Demo2 FEM 模态导入流程，完成 CSV 映射脚本、mapped mode 文件和 `codedFixedValue` 读取验证。 |
