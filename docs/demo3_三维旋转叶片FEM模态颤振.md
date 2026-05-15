# Demo 3：三维旋转叶片 FEM 模态颤振原型

## 1. 目标

Demo3 在 OpenFOAM 官方 propeller 滑移网格算例基础上，加入 FEM 模态输入，使三维旋转叶片表面同时具有：

$$
\mathrm{rigid\ rotation}
+
\mathrm{modal\ deformation}
$$

当前算例路径：

```text
demo3/propeller
```

核心运动形式：

$$
\boldsymbol{x}(t)
=
\boldsymbol{R}(\Omega t)\boldsymbol{x}_0
+
\boldsymbol{R}(\Omega t)
\left[
q(t)\boldsymbol{\phi}_0(\boldsymbol{x}_0)
\right]
$$

其中：

$$
q(t)=A\sin(2\pi ft+\varphi)
$$

## 2. 当前实现

原始 propeller 算例使用：

```cpp
motionSolver solidBody;
solidBodyMotionFunction rotatingMotion;
```

Demo3 改为：

```cpp
motionSolver solidBodyDisplacementLaplacian;
```

含义是：

```text
先对 innerCylinderSmall cellZone 做刚体旋转
再叠加 pointDisplacement 给出的叶片模态位移
内部网格位移由 Laplacian 平滑传播
```

当前旋转设置：

$$
\boldsymbol{\Omega}=158\,\boldsymbol{e}_y\ \mathrm{rad/s}
$$

对应文件：

```text
demo3/propeller/constant/dynamicMeshDict
```

## 3. FEM 模态输入

外部 FEM 软件需要导出叶片表面模态：

```csv
nodeId,x,y,z,phi_x,phi_y,phi_z
```

其中：

$$
\boldsymbol{x}_j^{FEM}
=
\begin{bmatrix}
x_j\\y_j\\z_j
\end{bmatrix}
$$

$$
\boldsymbol{\phi}_j^{FEM}
=
\begin{bmatrix}
\phi_{x,j}\\\phi_{y,j}\\\phi_{z,j}
\end{bmatrix}
$$

推荐 FEM 模态先做最大位移归一化：

$$
\max_j\left\|\boldsymbol{\phi}_j^{FEM}\right\|=1
$$

这样 OpenFOAM 中：

$$
A=\max\left\|\boldsymbol{u}\right\|
$$

## 4. 多 Patch 映射

propeller 表面由多个 patch 组成：

```text
propellerTip
propellerStem1
propellerStem2
propellerStem3
```

映射脚本：

```text
scripts/map_fem_mode_to_patches.py
```

输出：

```text
demo3/propeller/constant/modeShapes/propellerMode1_mapped.csv
```

格式：

```csv
patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance
```

映射公式：

$$
j^\*=
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

## 5. 运行方式

使用外部 FEM 模态：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3/propeller
FEM_MODE_CSV=/path/to/mode1_surface.csv ./Allrun
```

如果没有给 `FEM_MODE_CSV`，`Allrun` 会生成一个 sample mode，用来验证链路：

```text
constant/modeShapes/femMode1_sample.csv
constant/modeShapes/propellerMode1_mapped.csv
```

sample mode 只用于代码验证，不代表真实叶片模态。

## 6. 模态参数

模态运动参数在：

```text
demo3/propeller/constant/modeShapes/modeProperties
```

当前字段：

```cpp
modeFile        propellerMode1_mapped.csv;
amplitude       0.001;
frequency       100;
phase           0;
origin          (0 0 0);
axis            (0 1 0);
rotorOmega      158;
```

实际工程计算时，`frequency` 应替换为 FEM 第 \(m\) 阶模态频率：

$$
f=f_m
$$

## 7. 当前验证

已完成一次短程验证：

```text
Mapped 30416 patch points across 4 patches
Maximum nearest-node distance: 0
```

运行 `pimpleFoam -noFunctionObjects` 一个时间步，日志显示四个 patch 都成功读入模态：

```text
Loaded propeller FEM mode for patch "propellerTip"
Loaded propeller FEM mode for patch "propellerStem1"
Loaded propeller FEM mode for patch "propellerStem2"
Loaded propeller FEM mode for patch "propellerStem3"
```

并完成：

```text
Solving for cellDisplacementx
Solving for cellDisplacementy
Solving for cellDisplacementz
Solving for Ux, Uy, Uz, p, epsilon, k
End
```

说明：

$$
\mathrm{FEM\ CSV}
\rightarrow
\mathrm{multi\ patch\ mapping}
\rightarrow
\mathrm{rotating\ modal\ pointDisplacement}
\rightarrow
\mathrm{solidBodyDisplacementLaplacian}
\rightarrow
\mathrm{AMI\ propeller\ transient}
$$

链路已经跑通。

## 8. 后续升级

1. 用真实三维结构 FEM 模态替换 sample mode。
2. 从最近邻映射升级到 IDW/RBF。
3. 增加气动功：

$$
W=
\int_{t_0}^{t_0+T}
\int_{\Gamma}
\boldsymbol{t}\cdot\dot{\boldsymbol{u}}
\,dS\,dt
$$

4. 对多叶片颤振加入 IBPA：

$$
q_b(t)=A\sin(\omega t+b\sigma+\varphi)
$$

5. 后续将 `codedFixedValue` 升级为正式边界条件库。

## 9. 更新记录

| 日期 | 版本 | 内容 |
| --- | ---: | --- |
| 2026-05-15 | 0.1 | 建立 Demo3 三维旋转 propeller FEM 模态输入原型，完成多 patch 映射、旋转模态位移和短程求解验证。 |
