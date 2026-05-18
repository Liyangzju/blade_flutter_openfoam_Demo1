# Demo 3：六叶片旋转 FEM 模态颤振原型

## 1. 目标

Demo3 将三维旋转叶轮算例升级为“旋转刚体运动 + FEM 模态变形 + 叶片相位控制”的六叶片颤振原型。

| 模块 | 当前实现 |
| --- | --- |
| 叶片 patch | `blade1` 到 `blade6` |
| 结构模态 | CalculiX 壳单元模态 |
| 模态映射 | FEM surface mode CSV 映射到 OpenFOAM `blade.*` patch |
| 动网格 | `solidBodyDisplacementLaplacian` |
| 相位控制 | `ibpa`，相邻叶片相位差 |

当前主算例路径：

```text
demo3/
```

旧版 propeller 原型保留在：

```text
demo3/propeller.org/
```

## 2. 当前实现

当前 Demo3 使用：

```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;
motionSolver    solidBodyDisplacementLaplacian;
```

它表示：

1. `rotter.SLDPRT.rotor` cellZone 做刚体旋转。
2. `blade1` 到 `blade6` patch 叠加 FEM 模态位移。
3. 内部网格位移由 Laplacian 平滑传播。

对应文件：

```text
demo3/constant/dynamicMeshDict
```

当前旋转设置：

| 参数 | 值 |
| --- | --- |
| `origin` | `(0 0 0)` |
| `axis` | `(0 0 1)` |
| `omega` | `158 rad/s` |

## 3. FEM 全流程

Demo3 当前计划直接使用 CalculiX 求模态，而不是只依赖外部 FEM CSV。

一键流程在：

```text
demo3/Allrun
```

流程如下：

```text
foamFormatConvert
-> build_calculix_shell_from_patches.py
-> ccx six_blade_shell_modal
-> extract_calculix_modes.py
-> 自动选择第一条正频率模态
-> map_fem_mode_to_patches.py
-> decomposePar
-> pimpleFoam
-> reconstructPar
```

CalculiX 建模脚本：

```text
scripts/build_calculix_shell_from_patches.py
```

默认参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `patch-regex` | `blade.*|hub` | 读取六个叶片和 hub |
| `root-patch-regex` | `hub` | 用 hub 辅助定义根部约束 |
| `axis` | `(0 0 1)` | 转轴方向 |
| `root-ratio` | `0.08` | 靠近转轴的根部半径比例 |
| `thickness` | `1e-5` | 原型壳厚 |
| `min-area` | `1e-8` | 极瘦小三角过滤阈值 |

也就是用六个叶片建壳模型，并把 hub 与靠近轴线的根部区域作为 `ROOT` 节点集固定。

由于 CFD 表面包含薄叶片尖边，脚本还会：

1. 将表面 face 拆成三角壳单元。
2. 跳过极瘦小三角单元。
3. 当共享点两侧法向差超过 `45 deg` 时，自动拆分 CalculiX 节点。
4. 默认不把 root patch 本身作为自由壳面参与模态，只用于辅助选根部约束。

## 4. 模态输入与映射

CalculiX 输出经脚本提取后形成：

```text
demo3/fem/surface_modes/mode_01.csv
demo3/fem/surface_modes/mode_frequencies.csv
```

映射回 OpenFOAM 后形成：

```text
demo3/constant/modeShapes/bladeMode1_mapped.csv
```

格式：

```csv
patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance
```

当前临时壳模型可能出现零频机构模态，因此 `Allrun` 会自动选择第一条正频率模态，并把其频率写回：

```text
demo3/constant/modeShapes/modeProperties
```

## 5. 叶片相位控制

叶片模态位移在：

```text
demo3/0/pointDisplacement
```

边界条件匹配：

```text
"blade.*"
```

每个叶片的模态坐标写为：

$$
\begin{aligned}
q_b(t)
&=
A\sin\left(2\pi f t+\varphi+b\sigma\right),
\\
b
&=
0,1,\dots,5.
\end{aligned}
$$

变量含义：

| 符号 | 对应字段 | 含义 |
| --- | --- | --- |
| \(A\) | `amplitude` | 模态幅值 |
| \(f\) | `frequency` | 当前选中模态频率 |
| \(\varphi\) | `phase` | 整体初相位 |
| \(b\) | `bladeIndex` | 叶片编号，`blade1` 为 0 |
| \(\sigma\) | `ibpa` | 相邻叶片相位差 |

叶片编号：

| patch | \(b\) |
| --- | ---: |
| `blade1` | 0 |
| `blade2` | 1 |
| `blade3` | 2 |
| `blade4` | 3 |
| `blade5` | 4 |
| `blade6` | 5 |

参数文件：

```text
demo3/constant/modeShapes/modeProperties
```

关键字段：

```cpp
modeFile        bladeMode1_mapped.csv;
amplitude       0.001;
frequency       0.210018;
phase           0;
ibpa            0;
origin          (0 0 0);
axis            (0 0 1);
rotorOmega      158;
```

六叶片常用相位：

| `ibpa` | 相邻叶片相位差 | 含义 |
| --- | --- | --- |
| `0` | \(0^\circ\) | 所有叶片同相 |
| `pi/3` | \(60^\circ\) | 六叶片相邻相位差 |
| `pi` | \(180^\circ\) | 相邻叶片反相 |

## 6. 运行方式

加载 OpenFOAM 环境：

```bash
source /home/liyang/openFoam/OpenFOAM-v2112/etc/bashrc
```

运行 Demo3：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./Allrun
```

清理 Demo3 生成结果：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./Allclean
```

## 7. 查看 FEM 模态

CalculiX GraphiX (`cgx`) 当前环境没有安装。为了方便查看模态，Demo3 提供了一个 VTK 导出脚本：

```text
demo3/AllviewFem
```

默认行为：

1. 读取 `fem/surface_modes/mode_frequencies.csv`。
2. 自动选择第一条正频率模态。
3. 将该模态映射到 `blade.*` patch。
4. 导出 ParaView 可读的 legacy VTK surface。

默认导出：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./AllviewFem
```

当前会生成：

```text
fem/view/mode_05_scale_0.05.vtk
```

打开方式：

```bash
paraview fem/view/mode_05_scale_0.05.vtk
```

也可以指定模态阶次和显示放大倍数：

```bash
MODE=06 SCALE=0.05 ./AllviewFem
MODE=05 SCALE=0.005 ./AllviewFem
```

导出的 VTK 中：

| 数据 | 含义 |
| --- | --- |
| 点坐标 | `x + SCALE * phi`，用于直接查看放大振型 |
| `phi` | 原始归一化模态向量 |
| `phiMag` | 模态向量幅值 |
| `originalPosition` | 原始未变形坐标 |
| `patchId` | 叶片 patch 编号 |

## 8. 当前状态

截至 2026-05-18，Demo3 已完成：

1. 最新 Demo3 主算例迁移到 `demo3/` 根目录。
2. 确认 `blade1` 到 `blade6` 六个叶片 patch。
3. 确认旋转轴为 `(0 0 1)`，cellZone 为 `rotter.SLDPRT.rotor`。
4. 将动网格改为 `solidBodyDisplacementLaplacian`。
5. 添加 `blade.*` 的 `codedFixedValue` 模态位移。
6. 添加 `ibpa` 相位控制。
7. 添加多 patch CalculiX 壳模型生成脚本。
8. 将 CalculiX 求模态、模态提取、映射和 `pimpleFoam` 接入 `demo3/Allrun`。

验证结果：

| 项目 | 结果 |
| --- | --- |
| CalculiX 模态求解 | 成功输出 6 阶模态 |
| 第 1-4 阶 | `0 Hz` 机构模态 |
| 第 5 阶 | 第一条正频率模态，约 `0.210018 Hz` |
| FEM 到 CFD 映射 | `mode_05` 映射到 `blade1...blade6` |
| 最大最近点距离 | `0` |
| OpenFOAM 单步验证 | 真实网格 `pimpleFoam` 单步完成 |

真实网格单步验证中，六个 blade patch 均成功读入模态，并完成：

```text
cellDisplacementx/y/z
U, p, epsilon, k
```

轻量检查命令：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion
bash -n demo3/Allrun
bash -n demo3/Allclean
python3 -m py_compile \
    scripts/build_calculix_shell_from_patches.py \
    scripts/map_fem_mode_to_patches.py \
    scripts/extract_calculix_modes.py
```

再做 OpenFOAM 字典检查：

```bash
foamDictionary demo3/constant/dynamicMeshDict
foamDictionary demo3/0/pointDisplacement
foamDictionary demo3/constant/modeShapes/modeProperties
foamDictionary demo3/system/fvSolution
```

注意：`pimpleFoam -dry-run` 会进入 simplified mesh 分支，当前对 `blade.*` patch 匹配不可靠。验证动网格和模态边界条件时，应使用真实网格短跑。

## 9. 后续升级

1. 根据真实叶片材料更新 CalculiX 的 `young`、`density`、`poisson` 和 `thickness`。
2. 用更明确的 FEM 根部节点集替代简单的 `hub + root-ratio` 自动选根。
3. 将最近邻映射升级为 IDW 或 RBF。
4. 增加多阶模态和模态叠加。
5. 增加气动功和气动阻尼后处理：

$$
W
=
\int_{t_0}^{t_0+T}
\int_{\Gamma}
\boldsymbol{t}\cdot\dot{\boldsymbol{u}}
\,\mathrm{d}S\,\mathrm{d}t
$$

6. 扫描不同 `ibpa`，建立多叶片颤振相位分析流程。
7. 后续将 `codedFixedValue` 升级为正式边界条件库。

## 10. 更新记录

| 日期 | 版本 | 内容 |
| --- | ---: | --- |
| 2026-05-18 | 0.5 | 添加 `AllviewFem` 和 VTK 模态导出流程，用于在 ParaView 中查看计算模态。 |
| 2026-05-18 | 0.4 | 优化 Markdown 排版、公式显示、参数表格和验证结果表格。 |
| 2026-05-18 | 0.3 | 跑通 CalculiX 六叶片模态求解、第一条正频率模态自动选择、mode_05 映射和 OpenFOAM 真实网格单步验证。 |
| 2026-05-18 | 0.2 | 升级为六叶片 Demo3 主线，加入 CalculiX 全流程、`blade.*` 映射和 IBPA 相位控制说明。 |
| 2026-05-15 | 0.1 | 建立三维旋转 propeller FEM 模态输入原型，完成多 patch 映射、旋转模态位移和短程求解验证。 |
