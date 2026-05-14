# Demo 1：二维翼型自定义模态振动

## 1. 目标

本 Demo 的目标是在 OpenFOAM 官方 `wingMotion` 算例基础上，去掉原始刚体六自由度运动模型，改为由用户自定义的二维翼型给定模态振动驱动动网格。

当前算例路径：

```text
~/OpenFOAM/liyang-v2112/run/wingMotion/wingMotion2D_pimpleFoam
```

当前 Demo 属于解耦颤振分析路线：

```math
\boldsymbol{u}_s(\boldsymbol{x},t)
=
q(t)\,\boldsymbol{\phi}(\boldsymbol{x})
```

其中，结构运动不是由 CFD 气动力反算得到，而是预先给定。CFD 负责计算该给定运动诱导的非定常流场和气动力。

## 2. 原始算例与改造方向

OpenFOAM 官方 `wingMotion2D_pimpleFoam` 原始使用：

```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;
motionSolverLibs (sixDoFRigidBodyMotion);
motionSolver    sixDoFRigidBodyMotion;
```

该模型描述刚体六自由度运动。翼型表面运动由 `sixDoFRigidBodyMotion` 根据质量、惯量、弹簧、阻尼和约束计算。

本 Demo 改为：

```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;
motionSolverLibs (fvMotionSolvers);
motionSolver    displacementLaplacian;
diffusivity     inverseDistance 1(wing);
```

含义：

```math
\nabla \cdot \left(\gamma \nabla \boldsymbol{d}\right)=0
```

其中：

```math
\boldsymbol{d}
=
\boldsymbol{x}_{mesh}(t)-\boldsymbol{x}_{mesh}(0)
```

`wing` patch 上的 `pointDisplacement` 由自定义边界条件给定，内部网格位移由 `displacementLaplacian` 平滑传播。

## 3. 二维自定义振动数学模型

当前采用一个解析的二维弦向模态作为最小 Demo：

```math
\boldsymbol{u}(x,t)
=
\begin{bmatrix}
0 \\
q(t)\,\phi(\xi) \\
0
\end{bmatrix}
```

弦向无量纲坐标：

```math
\xi
=
\frac{x-x_{LE}}{c}
```

限制范围：

```math
\xi \in [0,1]
```

模态坐标：

```math
q(t)
=
A\sin(2\pi f t+\varphi)
```

解析模态形状：

```math
\phi(\xi)
=
\sin(\pi \xi)
```

因此当前边界位移为：

```math
\boldsymbol{u}(x,t)
=
\begin{bmatrix}
0 \\
A\sin(2\pi f t+\varphi)\sin(\pi\xi) \\
0
\end{bmatrix}
```

当前参数：

```math
A=0.015\ \mathrm{m}
```

```math
f=20\ \mathrm{Hz}
```

```math
\varphi=0
```

```math
x_{LE}=0
```

```math
c=1
```

周期：

```math
T=\frac{1}{f}=0.05\ \mathrm{s}
```

角频率：

```math
\omega=2\pi f
```

模态速度：

```math
\dot{\boldsymbol{u}}(x,t)
=
\begin{bmatrix}
0 \\
A(2\pi f)\cos(2\pi f t+\varphi)\sin(\pi\xi) \\
0
\end{bmatrix}
```

## 4. OpenFOAM 文件改动

### 4.1 `constant/dynamicMeshDict`

当前文件：

```text
wingMotion2D_pimpleFoam/constant/dynamicMeshDict
```

核心设置：

```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;

motionSolverLibs (fvMotionSolvers);

motionSolver    displacementLaplacian;

diffusivity     inverseDistance 1(wing);
```

该设置表示：

```math
\boldsymbol{u}_{wing}
\longrightarrow
\boldsymbol{d}_{mesh}
```

即 `wing` 上给定位移，内部网格通过拉普拉斯位移方程跟随变形。

### 4.2 `0/pointDisplacement`

当前文件：

```text
wingMotion2D_pimpleFoam/0/pointDisplacement
```

`wing` patch 设置为：

```cpp
wing
{
    type            codedFixedValue;
    name            modalWingDisplacement;
    value           uniform (0 0 0);

    code
    #{
        ...
    #};
}
```

`codedFixedValue` 表示 OpenFOAM 在运行时将 `code #{ ... #};` 中的 C++ 代码生成、编译为动态库，并在边界条件更新时调用。

动态库生成目录：

```text
wingMotion2D_pimpleFoam/dynamicCode/
```

当前已生成库示例：

```text
dynamicCode/platforms/linux64GccDPInt32Opt/lib/libmodalWingDisplacement_*.so
```

## 5. `codedFixedValue` 代码结构

当前核心代码：

```cpp
const scalar t = this->db().time().value();

const scalar amplitude = 0.015;
const scalar frequency = 20.0;
const scalar phase = 0.0;
const scalar xLeadingEdge = 0.0;
const scalar chord = 1.0;

const scalar q =
    amplitude
   *sin(constant::mathematical::twoPi*frequency*t + phase);

const pointField& pts = this->patch().localPoints();
vectorField disp(pts.size(), vector::zero);

forAll(pts, pointi)
{
    scalar xi = (pts[pointi].x() - xLeadingEdge)/chord;
    xi = min(max(xi, scalar(0)), scalar(1));

    const scalar phi =
        sin(constant::mathematical::pi*xi);

    disp[pointi] = vector(0, q*phi, 0);
}

operator==(disp);
```

对应关系：

```math
t
\leftarrow
\mathrm{Time.value()}
```

```math
q
\leftarrow
A\sin(2\pi f t+\varphi)
```

```math
\xi_i
\leftarrow
\frac{x_i-x_{LE}}{c}
```

```math
\phi_i
\leftarrow
\sin(\pi\xi_i)
```

```math
\boldsymbol{d}_i
\leftarrow
\begin{bmatrix}
0 \\
q\phi_i \\
0
\end{bmatrix}
```

```math
\mathrm{pointDisplacement}_{wing}
\leftarrow
\{\boldsymbol{d}_i\}_{i=1}^{N_p}
```

其中：

```math
N_p
=
\mathrm{size}(\mathrm{wing.localPoints})
```

## 6. C++ 数据结构对应关系

### 6.1 `scalar`

```cpp
scalar
```

对应：

```math
\mathbb{R}
```

在当前代码中：

```cpp
const scalar t = ...
const scalar amplitude = ...
const scalar q = ...
```

### 6.2 `pointField`

```cpp
const pointField& pts = this->patch().localPoints();
```

对应：

```math
\{\boldsymbol{x}_i\}_{i=1}^{N_p}
```

其中：

```math
\boldsymbol{x}_i
=
\begin{bmatrix}
x_i \\
y_i \\
z_i
\end{bmatrix}
```

### 6.3 `vectorField`

```cpp
vectorField disp(pts.size(), vector::zero);
```

对应：

```math
\{\boldsymbol{d}_i\}_{i=1}^{N_p}
```

初始值：

```math
\boldsymbol{d}_i
=
\begin{bmatrix}
0 \\
0 \\
0
\end{bmatrix}
```

循环更新后：

```math
\boldsymbol{d}_i
=
\begin{bmatrix}
0 \\
q(t)\phi(\xi_i) \\
0
\end{bmatrix}
```

### 6.4 `forAll`

```cpp
forAll(pts, pointi)
{
    ...
}
```

对应：

```math
i=1,2,\dots,N_p
```

### 6.5 `operator==(disp)`

```cpp
operator==(disp);
```

对应：

```math
\boldsymbol{d}_{boundary}
=
\mathrm{disp}
```

在 OpenFOAM 的 `fixedValuePointPatchField<vector>` 中，`operator==` 被重载为边界值赋值操作。

## 7. 自动生成代码的位置

`codedFixedValue` 会生成如下文件：

```text
dynamicCode/modalWingDisplacement/fixedValuePointPatchFieldTemplate.C
dynamicCode/modalWingDisplacement/fixedValuePointPatchFieldTemplate.H
dynamicCode/modalWingDisplacement/Make/files
dynamicCode/modalWingDisplacement/Make/options
```

核心函数：

```cpp
void modalWingDisplacementFixedValuePointPatchVectorField::updateCoeffs()
{
    if (this->updated())
    {
        return;
    }

    // code #{ ... #}; 被插入到这里

    this->parent_bctype::updateCoeffs();
}
```

OpenFOAM 调用顺序可简化为：

```math
t^n
\longrightarrow
\mathrm{updateCoeffs}
\longrightarrow
\boldsymbol{u}_{wing}^n
\longrightarrow
\boldsymbol{d}_{mesh}^n
\longrightarrow
\mathrm{CFD}
```

## 8. 运行流程

进入算例目录：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/wingMotion2D_pimpleFoam
```

串行运行：

```bash
pimpleFoam
```

查看动网格：

```bash
paraFoam
```

若需要重新并行：

```bash
decomposePar
mpirun -np 8 pimpleFoam -parallel
reconstructPar
```

## 9. 验证量

### 9.1 位移周期

```math
T=\frac{1}{20}=0.05\ \mathrm{s}
```

### 9.2 最大位移

```math
\max_{\xi,t}\left|\boldsymbol{u}\right|
=
A
=
0.015\ \mathrm{m}
```

### 9.3 最大速度

```math
\max_{\xi,t}\left|\dot{\boldsymbol{u}}\right|
=
A\,2\pi f
```

代入当前参数：

```math
\max_{\xi,t}\left|\dot{\boldsymbol{u}}\right|
=
0.015\times 2\pi \times 20
\approx
1.885\ \mathrm{m/s}
```

### 9.4 单周期气动功

瞬时功率：

```math
P(t)
=
\int_{\Gamma_w}
\boldsymbol{t}_f(\boldsymbol{x},t)
\cdot
\dot{\boldsymbol{u}}(\boldsymbol{x},t)
\ \mathrm{d}\Gamma
```

单周期气动功：

```math
W
=
\int_{t_0}^{t_0+T}
P(t)\ \mathrm{d}t
```

符号约定：

```math
W>0
```

```math
W<0
```

项目中约定：

```math
W>0
\Rightarrow
\mathrm{flutter\ risk}
```

```math
W<0
\Rightarrow
\mathrm{stable}
```

## 10. 升级到 FEM 模态的接口

当前解析模态：

```math
\boldsymbol{\phi}(\boldsymbol{x}_i)
=
\begin{bmatrix}
0 \\
\sin(\pi\xi_i) \\
0
\end{bmatrix}
```

FEM 导入后替换为：

```math
\boldsymbol{\phi}(\boldsymbol{x}_i)
=
\begin{bmatrix}
\phi_x(\boldsymbol{x}_i) \\
\phi_y(\boldsymbol{x}_i) \\
\phi_z(\boldsymbol{x}_i)
\end{bmatrix}
```

总位移：

```math
\boldsymbol{u}(\boldsymbol{x}_i,t)
=
q(t)\boldsymbol{\phi}(\boldsymbol{x}_i)
```

多模态：

```math
\boldsymbol{u}(\boldsymbol{x}_i,t)
=
\sum_{m=1}^{N_m}
q_m(t)\boldsymbol{\phi}_m(\boldsymbol{x}_i)
```

FEM 映射文件建议：

```text
constant/modeShapes/wingMode1_mapped.csv
```

建议字段：

```csv
patchPointI,x,y,z,phi_x,phi_y,phi_z
```

之后可将当前代码中的：

```cpp
const scalar phi =
    sin(constant::mathematical::pi*xi);

disp[pointi] = vector(0, q*phi, 0);
```

替换为：

```cpp
const vector phi = modeShape[pointi];

disp[pointi] = q*phi;
```

## 11. 当前 Demo 的定位

当前 Demo 不求解结构方程：

```math
\boldsymbol{M}\ddot{\boldsymbol{u}}
+
\boldsymbol{C}\dot{\boldsymbol{u}}
+
\boldsymbol{K}\boldsymbol{u}
=
\boldsymbol{F}_{aero}
```

当前 Demo 只给定：

```math
\boldsymbol{u}
=
q(t)\boldsymbol{\phi}
```

因此它属于：

```math
\mathrm{FEM}
\rightarrow
\mathrm{CFD}
```

而不是：

```math
\mathrm{CFD}
\leftrightarrow
\mathrm{FEM}
```

该 Demo 的价值是验证：

```math
\boldsymbol{\phi}(\boldsymbol{x})
\rightarrow
\boldsymbol{u}_{wing}(t)
\rightarrow
\boldsymbol{d}_{mesh}(t)
\rightarrow
\boldsymbol{F}_{aero}(t)
\rightarrow
W
```

后续可在此基础上接入真实 FEM 模态、IBPA 扫描和气动阻尼后处理。

## 12. 更新记录

| 日期 | 版本 | 内容 |
| --- | ---: | --- |
| 2026-05-14 | 0.1 | 建立 Demo 1 二维自定义振动技术路线，记录解析模态、OpenFOAM 实现与 FEM 模态升级接口。 |
