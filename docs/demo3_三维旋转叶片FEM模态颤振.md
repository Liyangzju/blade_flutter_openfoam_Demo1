# Demo 3：PrePoMax 结构模态驱动的六叶片旋转颤振原型

## 1. 目标

Demo3 现在采用独立结构网格路线：PrePoMax/CalculiX 负责结构模态计算，OpenFOAM 读取映射后的模态位移并驱动六叶片旋转动网格。

```text
PrePoMax / CalculiX 结构模态
-> 读取 .frd 中的模态位移 DISP
-> 提取 mode_XX.csv
-> 映射到 OpenFOAM blade.* patch
-> 旋转刚体运动 + 叶片模态振动
```

当前 Demo3 不再从 CFD patch 反向生成 CalculiX 壳单元模型。结构网格、材料、约束和 Frequency Step 都在 PrePoMax 中完成。

| 模块 | 当前实现 |
| --- | --- |
| 叶片 patch | `blade1` 到 `blade6` |
| 结构模态 | PrePoMax/CalculiX 实体 FEM 模态 |
| 结果来源 | `demo3/fem/prepomax/Analysis-1.frd` |
| 模态提取 | `scripts/extract_calculix_frd_modes.py` |
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

## 3. PrePoMax 文件

当前结构模态文件放在：

```text
demo3/fem/prepomax/
```

核心文件：

```text
Analysis-1.inp   CalculiX 输入模型：节点、单元、材料、约束、Frequency Step
Analysis-1.dat   文本摘要：频率、模态参与因子、有效模态质量
Analysis-1.frd   完整结果：节点坐标、单元连接、每阶模态位移/应力/应变
```

三文件格式和关键片段说明见：

```text
docs/PrePoMax_CalculiX三文件结构说明.md
```

当前 `Analysis-1.inp` 中已经命名了结构表面：

```text
Surface, Name=blade1
Surface, Name=blade2
Surface, Name=blade3
Surface, Name=blade4
Surface, Name=blade5
Surface, Name=blade6
Surface, Name=hub
```

当前结构模型信息：

| 项目 | 值 |
| --- | ---: |
| 节点数 | `105387` |
| 单元数 | `60643` |
| 单元类型 | `C3D10` 二阶四面体实体单元 |
| 密度 | `2700 kg/m3` |
| 弹性模量 | `70 GPa` |
| 泊松比 | `0.33` |
| 固定节点数 | `2269` |
| 模态数 | `10` |

## 4. FRD 位移提取与映射

`Analysis-1.frd` 中每阶模态都有：

```text
DISP      位移，也就是模态振型
STRESS    应力
TOSTRAIN  总应变
FORC      力/反力
```

Demo3 只使用 `DISP` 的 `D1/D2/D3` 分量，并写成：

```csv
nodeId,x,y,z,phi_x,phi_y,phi_z
```

提取脚本：

```text
scripts/extract_calculix_frd_modes.py
```

输出目录：

```text
demo3/fem/structural_modes/
```

输出文件：

```text
mode_frequencies.csv
mode_01.csv
mode_02.csv
...
mode_10.csv
```

提取时默认使用 `.inp` 里的命名 surface：

```text
blade.*
```

也就是只提取 `blade1` 到 `blade6` 的结构表面节点，不再把 hub 外表面节点混入 `mode_XX.csv`。如果没有命名 surface，脚本仍可用 `--surface-only` 回退到“全部外表面节点”。

当前 `blade.*` 命名 surface 提取结果：

| 项目 | 数量 |
| --- | ---: |
| FEM 总节点 | `105387` |
| 六个 blade surface 节点 | `34458` |
| OpenFOAM `blade.*` patch 点 | `7113` |

映射回 OpenFOAM 后形成：

```text
demo3/constant/modeShapes/bladeMode1_mapped.csv
```

格式：

```csv
patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance
```

`sourceDistance` 是 OpenFOAM patch 点到最近 FEM 模态节点的距离，用来判断结构网格和 CFD 网格是否对齐。

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
frequency       273.9662797;
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

指定第 10 阶模态运行：

```bash
MODE=10 ./Allrun
```

只提取并使用第 10 阶：

```bash
EXTRACT_MODES=10 MODE=10 ./Allrun
```

`Allrun` 当前流程：

```text
foamFormatConvert
-> extract_calculix_frd_modes.py 读取 Analysis-1.inp 中的 blade.* surface
-> 选择模态
-> 写入 modeProperties/frequency
-> map_fem_mode_to_patches.py
-> decomposePar
-> pimpleFoam
-> reconstructPar
```

常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PREPOMAX_FRD` | `fem/prepomax/Analysis-1.frd` | PrePoMax/CalculiX 结果文件 |
| `PREPOMAX_INP` | `fem/prepomax/Analysis-1.inp` | 含命名 surface 的 CalculiX 输入文件 |
| `FEM_SURFACE_REGEX` | `blade.*` | 要提取的 PrePoMax surface 名称 |
| `MODE` | 空 | 指定映射到 OpenFOAM 的模态阶次 |
| `EXTRACT_MODES` | 空 | 只提取指定模态，例如 `10` |

清理 Demo3 生成结果：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3
./Allclean
```

`Allclean` 会清理派生模态和旧反建 FEM 目录，但保留用户导入的：

```text
fem/prepomax/
```

## 7. 查看 FEM 模态

CalculiX GraphiX (`cgx`) 当前环境没有安装。为了方便查看模态，Demo3 提供了一个 VTK 导出脚本：

```text
demo3/AllviewFem
```

默认行为：

1. 读取 `fem/structural_modes/mode_frequencies.csv`。
2. 如果模态 CSV 不存在，则从 `fem/prepomax/Analysis-1.frd` 提取。
3. 将该模态映射到 `blade.*` patch。
4. 导出 ParaView 可读的 legacy VTK surface。

默认导出：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion/demo3
MODE=10 SCALE=0.05 ./AllviewFem
```

当前会生成：

```text
fem/view/mode_10_scale_0.05.vtk
```

打开方式：

```bash
paraview fem/view/mode_10_scale_0.05.vtk
```

也可以指定模态阶次和显示放大倍数：

```bash
MODE=10 SCALE=0.05 ./AllviewFem
MODE=07 SCALE=0.005 ./AllviewFem
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

截至 2026-05-19，Demo3 已完成：

1. 最新 Demo3 主算例迁移到 `demo3/` 根目录。
2. 确认 `blade1` 到 `blade6` 六个叶片 patch。
3. 确认旋转轴为 `(0 0 1)`，cellZone 为 `rotter.SLDPRT.rotor`。
4. 将动网格改为 `solidBodyDisplacementLaplacian`。
5. 添加 `blade.*` 的 `codedFixedValue` 模态位移。
6. 添加 `ibpa` 相位控制。
7. 接入 PrePoMax/CalculiX `.frd` 模态位移提取。
8. 使用 PrePoMax 命名 surface `blade1...blade6` 只提取叶片结构表面节点。
9. 删除 Demo3 主流程中从 CFD patch 反建 FEM 的内容。
10. 将 FRD 模态提取、映射和 `pimpleFoam` 接入 `demo3/Allrun`。

验证结果：

| 项目 | 结果 |
| --- | --- |
| PrePoMax/CalculiX 模态 | 成功输出 10 阶模态 |
| 第 1-6 阶 | 约 `62.2 Hz` |
| 第 7-10 阶 | 约 `273.9 Hz` |
| FEM 到 CFD 映射 | 从 `fem/structural_modes/mode_XX.csv` 映射到 `blade1...blade6` |
| 反建 FEM 流程 | 已从 Demo3 主流程移除 |

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
    scripts/extract_calculix_frd_modes.py \
    scripts/map_fem_mode_to_patches.py \
    scripts/export_mapped_mode_to_vtk.py
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

1. 对比 FEM 结构表面和 CFD 叶片 patch 的 `sourceDistance`，确认坐标、尺度和姿态一致。
2. 根据真实叶片材料更新 PrePoMax 中的材料和约束。
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
| 2026-05-19 | 0.6 | 切换为 PrePoMax/CalculiX FRD 模态提取与映射流程，移除 Demo3 从 CFD patch 反建 FEM 的主线。 |
| 2026-05-18 | 0.5 | 添加 `AllviewFem` 和 VTK 模态导出流程，用于在 ParaView 中查看计算模态。 |
| 2026-05-18 | 0.4 | 优化 Markdown 排版、公式显示、参数表格和验证结果表格。 |
| 2026-05-18 | 0.3 | 跑通 CalculiX 六叶片模态求解、第一条正频率模态自动选择、mode_05 映射和 OpenFOAM 真实网格单步验证。 |
| 2026-05-18 | 0.2 | 升级为六叶片 Demo3 主线，加入 CalculiX 全流程、`blade.*` 映射和 IBPA 相位控制说明。 |
| 2026-05-15 | 0.1 | 建立三维旋转 propeller FEM 模态输入原型，完成多 patch 映射、旋转模态位移和短程求解验证。 |
