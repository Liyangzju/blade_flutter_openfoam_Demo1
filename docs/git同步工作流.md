# Git 同步工作流

## 1. 目标

通过 Git 让 Linux/OpenFOAM 环境中的 Codex 和 Windows 环境中的 Codex 共享同一个叶片颤振开发项目。

推荐仓库根目录：

```text
~/OpenFOAM/liyang-v2112/run/wingMotion
```

Windows 端可以将同一个远程仓库 clone 到：

```text
H:\实习-叶片颤振
```

## 2. Linux 端安装 Git

当前 Linux 环境尚未安装 Git。需要在终端手动执行：

```bash
sudo apt-get update
sudo apt-get install -y git
```

安装后验证：

```bash
git --version
```

## 3. Linux 端初始化仓库

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion
git init
```

添加项目文件：

```bash
git add .gitignore README.md docs Allrun Allclean openParaFoam.sh
git add wingMotion2D_pimpleFoam/0 wingMotion2D_pimpleFoam/constant wingMotion2D_pimpleFoam/system
git add wingMotion2D_simpleFoam/0 wingMotion2D_simpleFoam/constant wingMotion2D_simpleFoam/system
git add wingMotion_snappyHexMesh/constant wingMotion_snappyHexMesh/system
```

提交：

```bash
git commit -m "Initial blade flutter demo workspace"
```

## 4. 远程仓库

添加远程仓库：

```bash
git remote add origin <your-remote-url>
git branch -M main
git push -u origin main
```

`<your-remote-url>` 可以是 GitHub、Gitee 或内部 Git 服务地址。

## 5. Windows 端同步

在 Windows 端：

```powershell
cd H:\实习-叶片颤振
git clone <your-remote-url> .
```

之后 Windows Codex 修改后：

```powershell
git add .
git commit -m "Update notes"
git push
```

Linux 端同步：

```bash
cd ~/OpenFOAM/liyang-v2112/run/wingMotion
git pull
```

## 6. 忽略规则

`.gitignore` 已配置为忽略：

```text
time directories
processor*/
postProcessing/
dynamicCode/
constant/polyMesh/
log.*
VTK/
ParaView files
```

这能避免把 OpenFOAM 计算结果、大型网格和动态编译产物提交到 Git。

## 7. 推荐协作习惯

每次 Linux 端运行计算前：

```bash
git pull
```

每次修改文档、脚本或算例字典后：

```bash
git status
git add <files>
git commit -m "<message>"
git push
```

计算结果如需归档，建议单独压缩保存，不进入 Git 主仓库。
