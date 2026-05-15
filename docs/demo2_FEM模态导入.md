# Demo 2：开源 FEM 模态导入驱动翼型振动

## 1. 目标

当前 Demo2 已拆成两个部分：

```text
demo2/demo2A  -> CalculiX 开源 FEM 模态计算
demo2/demo2B  -> OpenFOAM 读取 FEM 模态并驱动动网格
```

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
demo2/demo2A
demo2/demo2B
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
demo2/demo2A/calculix/wing_shell_modal.inp
demo2/demo2A/surface_modes/mode_frequencies.csv
demo2/demo2A/surface_modes/mode_01.csv
demo2/demo2B/constant/modeShapes/mode_frequencies.csv
demo2/demo2B/constant/modeShapes/wingMode1_mapped.csv
```

`mode_01.csv` 表示 CalculiX 求解并提取出来的第 1 阶表面模态。

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

## 5. 当前 CalculiX FEM 数据

当前 Demo2A 直接将 `demo2B` 的 `wing` patch 转成 CalculiX 壳单元模型。

运行：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo2/demo2A
./Allrun
```

`Allrun` 执行：

```text
OpenFOAM wing patch
  -> CalculiX shell model
  -> ccx frequency analysis
  -> mode_01.csv ... mode_06.csv
  -> wingMode1_mapped.csv
```

结构模态方程：

$$
\left(
\boldsymbol{K}
-
\omega^2\boldsymbol{M}
\right)
\boldsymbol{\Phi}
=
\boldsymbol{0}
$$

默认材料：

$$
E=70\times10^9\ \mathrm{Pa}
$$

$$
\nu=0.33
$$

$$
\rho=2700\ \mathrm{kg/m^3}
$$

壳厚度：

$$
h=1.0\times10^{-3}\ \mathrm{m}
$$

约束：

$$
\boldsymbol{u}\big|_{z=z_{\min}}=\boldsymbol{0}
$$

当前提取到的频率：

```text
mode 1: 461.955 Hz
mode 2: 487.599 Hz
mode 3: 524.925 Hz
mode 4: 578.086 Hz
mode 5: 595.724 Hz
mode 6: 629.825 Hz
```

当前映射结果：

```text
Mapped 756 patch points -> demo2/demo2B/constant/modeShapes/wingMode1_mapped.csv
Maximum nearest-node distance: 0
```

距离为 0 的原因是第一版 FEM 壳模型直接复用了 OpenFOAM `wing` patch 点。

## 6. `pointDisplacement` 实现

Demo2 中：

```text
demo2/demo2B/0/pointDisplacement
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

当前参数写在 `demo2/demo2B/0/pointDisplacement` 中：

$$
A=0.015\ \mathrm{m}
$$

$$
f=461.955\ \mathrm{Hz}
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
Solving for cellDisplacementx
Solving for cellDisplacementy
Solving for Ux
Solving for Uy
Solving for p
Solving for omega
Solving for k
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
| 2026-05-14 | 0.2 | 加入 CalculiX 开源 FEM 壳单元模态计算，完成 `demo2A -> demo2B` 一键链路。 |
| 2026-05-14 | 0.1 | 建立 Demo2 FEM 模态导入流程，完成 CSV 映射脚本、mapped mode 文件和 `codedFixedValue` 读取验证。 |
