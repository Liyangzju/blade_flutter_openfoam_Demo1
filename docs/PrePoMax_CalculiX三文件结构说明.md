# PrePoMax / CalculiX 三文件结构说明

本文说明 Demo3 中从 PrePoMax 导入的三个核心文件：

```text
demo3/fem/prepomax/Analysis-1.inp
demo3/fem/prepomax/Analysis-1.dat
demo3/fem/prepomax/Analysis-1.frd
```

它们的关系可以理解为：

```text
Analysis-1.inp  计算输入：网格、材料、约束、surface、Frequency Step
        ↓
CalculiX 求解
        ↓
Analysis-1.dat  文本摘要：频率、参与因子、有效模态质量
Analysis-1.frd  完整结果：节点坐标、单元连接、每阶位移/应力/应变
```

Demo3 当前使用：

```text
.inp  读取 blade1...blade6 的命名 surface
.frd  读取这些 surface 节点的模态位移 DISP
.dat  辅助查看频率和模态质量信息
```

## 1. Analysis-1.inp

`.inp` 是 CalculiX 输入文件，也就是“求解器要算什么”。它包含节点、单元、节点集、单元集、表面、材料、约束和模态分析步。

### 1.1 文件头与单位

```inp
*Heading
Hash: xf2VM4mZ, Date: 05/19/2026, Unit system: M_KG_S_C
```

这里说明模型使用：

```text
m, kg, s, deg C
```

也就是米、千克、秒、摄氏度。后面的坐标、密度、弹性模量都应和这个单位体系一致。

### 1.2 节点 `*Node`

```inp
*Node
1, -2.18066600E-002, 1.07588100E-001, -4.06963600E-001
2, -2.68525798E-002, 1.07913107E-001, -3.98903032E-001
```

每一行是一个 FEM 节点：

```text
nodeId, x, y, z
```

例如：

```text
节点 1:
x = -0.02180666 m
y =  0.10758810 m
z = -0.40696360 m
```

这些节点坐标也会被写入 `.frd`，用于后处理显示和结果映射。

### 1.3 单元 `*Element`

```inp
*Element, Type=C3D10, Elset=Solid_part-1
1, 12738, 15897, 14407, 14406, 52171, 52172, 52173, 52174, 52175, 52176
2, 12738, 14406, 14407, 12742, 52174, 52176, 52173, 52177, 52178, 52179
```

含义：

```text
单元编号, 组成该单元的节点编号...
```

当前单元类型是：

```text
C3D10
```

它是 10 节点二阶四面体实体单元：

| 节点位置 | 含义 |
| --- | --- |
| 前 4 个节点 | 四面体角点 |
| 后 6 个节点 | 四面体边中点 |

例如单元 1：

```text
element 1 =
12738, 15897, 14407, 14406,
52171, 52172, 52173, 52174, 52175, 52176
```

这些编号都能在 `*Node` 段里找到对应坐标。

### 1.4 节点集 `*Nset`

```inp
*Nset, Nset=Internal-1_blade3
382, 383, 384, 385, 386, 387, 388, 389, ...
```

`Nset` 是节点集合。这里表示：

```text
Internal-1_blade3 这个节点集合包含节点 382, 383, 384, ...
```

如果这个集合来自 PrePoMax 中对 blade3 的命名选择，那么它通常表示 blade3 相关区域的节点。

注意：

```text
Nset 描述“有哪些节点”
Surface 描述“哪些单元的哪些面”
```

对于 OpenFOAM 表面映射，`Surface` 的语义更精确。

### 1.5 单元集 `*Elset`

```inp
*Elset, Elset=Internal-1_blade3_S2
20, 22, 168, 178, 338, 375, 474, ...
```

`Elset` 是单元集合。这里表示：

```text
Internal-1_blade3_S2 这个单元集合包含 element 20, 22, 168, ...
```

这些数字是单元编号，不是节点编号。要找到某个单元的节点，需要回到 `*Element` 段查对应的 element id。

### 1.6 表面 `*Surface`

```inp
*Surface, Name=blade3, Type=Element
Internal-1_blade3_S2, S2
Internal-1_blade3_S4, S4
Internal-1_blade3_S3, S3
Internal-1_blade3_S1, S1
```

这段定义了名为 `blade3` 的结构表面。

含义是：

```text
blade3 表面 =
Internal-1_blade3_S2 这些单元的 S2 面
+ Internal-1_blade3_S4 这些单元的 S4 面
+ Internal-1_blade3_S3 这些单元的 S3 面
+ Internal-1_blade3_S1 这些单元的 S1 面
```

对于 C3D10 四面体，`S1...S4` 是四个三角面。当前脚本采用的面节点关系为：

| 面 | 对应 C3D10 局部节点 |
| --- | --- |
| `S1` | `1, 2, 3, 5, 6, 7` |
| `S2` | `1, 4, 2, 8, 9, 5` |
| `S3` | `2, 4, 3, 9, 10, 6` |
| `S4` | `3, 4, 1, 10, 8, 7` |

Demo3 当前正是通过这些 `Surface, Name=blade1...blade6` 判断哪些 FEM 节点属于叶片表面。

### 1.7 材料

```inp
*Material, Name=Material-1
*Density
2700
*Elastic
70000000000, 0.33
```

含义：

| 字段 | 含义 |
| --- | --- |
| `Density` | 密度，当前为 `2700 kg/m3` |
| `Elastic` 第 1 个数 | 弹性模量，当前为 `70 GPa` |
| `Elastic` 第 2 个数 | 泊松比，当前为 `0.33` |

### 1.8 实体截面

```inp
*Solid section, Elset=Internal_Selection-1_Solid_Section-1, Material=Material-1
```

表示这些实体单元使用 `Material-1`。因为当前是实体单元 `C3D10`，所以这里是 `Solid section`，不是 `Shell section`。

### 1.9 固定边界

```inp
*Boundary
Internal_Selection-1_Fixed-1, 1, 6, 0
```

含义是：

```text
对 Internal_Selection-1_Fixed-1 这个节点集，
约束第 1 到第 6 自由度为 0。
```

对实体单元来说，主要起作用的是平动自由度：

```text
U1 = 0
U2 = 0
U3 = 0
```

### 1.10 模态步和输出

```inp
*Step
*Frequency
10
```

表示求前 10 阶固有频率和振型。

```inp
*Node file
RF, U
*El file
S, E, NOE
```

输出内容：

| 字段 | 含义 |
| --- | --- |
| `U` | 节点位移，也就是模态振型 |
| `RF` | 反力 |
| `S` | 应力 |
| `E` | 应变 |
| `NOE` | 单元节点相关输出 |

Demo3 最关键的是 `U`，它会进入 `.frd` 的 `DISP` 结果块。

## 2. Analysis-1.dat

`.dat` 是 CalculiX 的文本摘要文件，适合快速查看频率、模态参与因子和有效模态质量。

### 2.1 固有频率表

```text
E I G E N V A L U E   O U T P U T

MODE NO    EIGENVALUE        FREQUENCY
...
1   0.1527280E+06   0.3908042E+03   0.6219843E+02
```

主要看这一列：

```text
CYCLES/TIME
```

它就是频率，单位为 Hz。

当前 10 阶频率：

| mode | frequency / Hz |
| ---: | ---: |
| 1 | `62.19842691` |
| 2 | `62.20391474` |
| 3 | `62.28986718` |
| 4 | `62.30918647` |
| 5 | `62.33774290` |
| 6 | `62.39446753` |
| 7 | `273.9024938` |
| 8 | `273.9064623` |
| 9 | `273.9301064` |
| 10 | `273.9662797` |

### 2.2 参与因子

```text
P A R T I C I P A T I O N   F A C T O R S

MODE NO.   X-COMPONENT  Y-COMPONENT  Z-COMPONENT  X-ROTATION ...
```

参与因子表示某阶模态在各个整体方向上的参与程度。它适合用来判断某阶模态更偏向哪个方向的整体运动。

### 2.3 有效模态质量

```text
E F F E C T I V E   M O D A L   M A S S
```

有效模态质量表示某阶模态对整体质量响应的贡献。它常用于判断前若干阶模态是否覆盖了足够的动力响应。

### 2.4 总有效质量

```text
T O T A L   E F F E C T I V E   M A S S
```

这是模型在各个方向上的总有效质量基准。可以和前面的有效模态质量累计值对比。

## 3. Analysis-1.frd

`.frd` 是 CalculiX 的完整结果文件，PrePoMax 的 Results 页面主要读取它。

它包含：

```text
文件头
节点坐标块
单元连接块
每阶模态的 DISP/STRESS/TOSTRAIN/FORC 结果块
结束标记 9999
```

### 3.1 文件头

```text
1C
1UHash: xf2VM4mZ, Date: 05/19/2026, Unit system: M_KG_S_C
1UPGM               CalculiX
1UVERSION           Version 2.21
```

说明这是 CalculiX 2.21 生成的 FRD 文件，单位体系同样是 `M_KG_S_C`。

### 3.2 节点坐标块

```text
2C                        105387                                     1
-1         1-2.18067E-02 1.07588E-01-4.06964E-01
-1         2-2.68526E-02 1.07913E-01-3.98903E-01
```

`2C` 表示节点坐标块开始，`105387` 是节点数。

每行格式是：

```text
-1 nodeId x y z
```

注意 FRD 是固定列宽格式，负数经常和前一个字段贴在一起：

```text
1-2.18067E-02
```

实际含义是：

```text
nodeId = 1
x = -2.18067E-02
```

因此脚本不能简单按空格切分所有 FRD 行，必须按固定列宽读取。

### 3.3 单元连接块

```text
3C                         60643                                     1
-1         1    6    0    1
-2     12738     15897     14407     14406     52171 ...
```

`3C` 表示单元块开始，`60643` 是单元数。

每个单元通常用两行表示：

```text
-1 elementId elementType ...
-2 node1 node2 node3 ...
```

这里 `elementType = 6`，对应当前模型中的 C3D10 四面体。

### 3.4 模态位移块 `DISP`

```text
1PMODE                         1
100CL  101 62.19842691      105387                     2    1MODAL      1
-4  DISP        4    1
-5  D1          1    2    1    0
-5  D2          1    2    2    0
-5  D3          1    2    3    0
-5  ALL         1    2    0    0    1ALL
-1         1 2.93906E-05 6.82379E-06 3.49736E-06
```

关键含义：

| 行 | 含义 |
| --- | --- |
| `1PMODE 1` | 第 1 阶模态 |
| `100CL ... 62.19842691 ... 105387` | 频率为 `62.19842691 Hz`，节点数 `105387` |
| `-4 DISP` | 下面是位移结果 |
| `D1` | x 方向位移，等价于 `U1` |
| `D2` | y 方向位移，等价于 `U2` |
| `D3` | z 方向位移，等价于 `U3` |
| `ALL` | 位移幅值 |

节点位移行：

```text
-1         1 2.93906E-05 6.82379E-06 3.49736E-06
```

表示第 1 阶模态下：

```text
node 1:
U1 = 2.93906e-05
U2 = 6.82379e-06
U3 = 3.49736e-06
```

### 3.5 其他结果块

每阶模态通常还有：

```text
STRESS
TOSTRAIN
FORC
```

含义：

| 结果块 | 含义 | Demo3 是否使用 |
| --- | --- | --- |
| `DISP` | 节点位移/模态振型 | 使用 |
| `STRESS` | 应力 | 暂不使用 |
| `TOSTRAIN` | 总应变 | 暂不使用 |
| `FORC` | 力/反力 | 暂不使用 |

Demo3 只读取 `DISP`。

## 4. Demo3 如何提取叶片模态

当前脚本：

```text
scripts/extract_calculix_frd_modes.py
```

典型命令：

```bash
python3 ../scripts/extract_calculix_frd_modes.py \
    --frd fem/prepomax/Analysis-1.frd \
    --inp fem/prepomax/Analysis-1.inp \
    --out-dir fem/structural_modes \
    --normalize max \
    --surface-regex 'blade.*'
```

流程：

```text
1. 从 .inp 读取 Surface, Name=blade1...blade6
2. 根据 Surface 中的 Elset 和 S1/S2/S3/S4 找到表面单元面
3. 从 C3D10 单元连接关系中反推出这些面上的节点编号
4. 从 .frd 中读取这些节点的 DISP 位移
5. 每阶模态按 max(|phi|)=1 归一化
6. 写出 mode_01.csv ... mode_10.csv
```

当前提取结果：

```text
FEM 总节点: 105387
六个 blade surface 节点: 34458
OpenFOAM blade patch 点: 7113
```

输出格式：

```csv
nodeId,x,y,z,phi_x,phi_y,phi_z
```

其中：

| 字段 | 来源 |
| --- | --- |
| `nodeId` | `.inp/.frd` 中的 FEM 节点编号 |
| `x,y,z` | `.frd` 节点坐标 |
| `phi_x,phi_y,phi_z` | `.frd` 中该模态的 `D1,D2,D3`，归一化后写出 |

## 5. 映射到 OpenFOAM

提取后，Demo3 使用：

```bash
python3 ../scripts/map_fem_mode_to_patches.py \
    --case . \
    --patch-regex 'blade.*' \
    --fem fem/structural_modes/mode_10.csv \
    --out constant/modeShapes/bladeMode1_mapped.csv
```

映射逻辑：

```text
1. 读取 OpenFOAM constant/polyMesh 中的 blade1...blade6 patch 点
2. 对每个 OpenFOAM patch 点，寻找最近的 FEM blade surface 节点
3. 把该 FEM 节点的 phi_x/phi_y/phi_z 写到 OpenFOAM patch 点上
```

输出格式：

```csv
patchName,patchPointI,x,y,z,phi_x,phi_y,phi_z,sourceNodeId,sourceDistance
```

关键字段：

| 字段 | 含义 |
| --- | --- |
| `patchName` | OpenFOAM patch 名称，如 `blade3` |
| `patchPointI` | 该 patch 内的局部点编号 |
| `phi_x,phi_y,phi_z` | 映射后的模态位移方向 |
| `sourceNodeId` | 最近的 FEM 节点编号 |
| `sourceDistance` | OpenFOAM 点和 FEM 节点之间的距离 |

`sourceDistance` 是判断 FEM 和 CFD 几何是否对齐的重要指标。当前最大值约：

```text
0.00385599 m
```

## 6. 常见问题

### 为什么 `mode_10.csv` 的节点数少于 `.inp` 总节点数？

因为 `.inp/.frd` 的 `105387` 是实体 FEM 总节点数，包含大量内部节点。OpenFOAM 的 `blade.*` 是表面 patch，所以 Demo3 只提取 `blade1...blade6` 的命名 surface 节点。

当前：

```text
总 FEM 节点: 105387
blade surface 节点: 34458
```

这是正常的。

### `Nset` 和 `Surface` 有什么区别？

```text
Nset    = 节点集合
Elset   = 单元集合
Surface = 单元的某些面组成的表面
```

对于表面映射，`Surface` 更准确，因为它明确描述了真实边界面。

### 如何找到 `Internal-1_blade3_S2` 对应的单元编号？

在 `.inp` 中搜索：

```inp
*Elset, Elset=Internal-1_blade3_S2
```

下面列出的数字就是单元编号：

```inp
20, 22, 168, 178, ...
```

再到 `*Element` 段中查这些 element id，就能找到对应 C3D10 单元的 10 个节点。

完整关系：

```text
Surface blade3
-> Internal-1_blade3_S2, S2
-> Elset Internal-1_blade3_S2
-> element id 列表
-> Element 连接关系
-> C3D10 的 S2 面节点
-> FRD 中这些节点的 DISP 位移
```

### `.frd` 中的模态位移是真实位移吗？

不是直接意义上的真实位移。模态振型主要表示相对形状，幅值可任意缩放。Demo3 会把每阶模态归一化到：

```text
max(|phi|) = 1
```

真实进入 OpenFOAM 的位移幅值由：

```text
constant/modeShapes/modeProperties
```

中的 `amplitude` 控制。
