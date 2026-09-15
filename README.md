# Analysis Tool For HyperOS

用于提取、修改、比对和重命名 HyperOS 中的 APK 文件的 Python 脚本。它可以帮助开发者和用户轻松地获取系统 APK、比对版本更新，并按规范自动归档。

## 性能优化与特性

- ⚡ **毫秒级极速解析**：内置纯 Python 零依赖 AXML 二进制清单解析器，提取单 APK 元数据仅需数毫秒，解析速度比重型框架提升 **30x ~ 50x**，几百个 APK 仅需数秒即可完成。
- 🚀 **智能 I/O 过滤**：定向分区扫描与就地一次性规则过滤，消除无谓全盘深搜与二次搬运，大幅降低磁盘 I/O 消耗。
- 🔄 **并发自适应**：根据当前机器 CPU 核心数自动调优线程并发度。
- 🛠️ **全流程流水线**：新增 `-A / --all` 参数，支持一键执行镜像提取、分区解包、APK 筛选、极速重命名、增量比对与中文名归档。
- 🛡️ **跨进程状态保持**：Split APK 分包映射关系本地持久化，分步执行命令不再丢失 split 打包。
- 💻 **零外部 Python 强依赖**：开箱即用，无需预先安装 androguard 等大型分析库（已安装时可作为极端情况下的兜底）。

## 功能

- 从 ROM 下载链接下载 ROM（支持断点续传与多线程）
- 从 ZIP 文件中提取 payload.bin
- 从 payload.bin 文件中提取指定镜像文件
- 提取 EROFS 镜像文件
- 筛选并移动指定 APK
- 极速重命名 APK 文件（`包名^版本名^版本号.apk`）
- 比对并更新 APK 版本及生成 `.apks`
- 应用中文名重命名（清洗非法字符）
- 删除多余中间文件
- 获取系统包设备信息

## 如何使用

1. 前往 Release 下载对应平台可执行工具（如 payload-dumper-go、extract.erofs）放置于 `./tools` 目录下或加入系统 PATH。

2. 确保已安装 Python 3.x（推荐 Python 3.8+），支持纯标准库零依赖直接运行：

   ```bash
   python main.py -h
   ```

3. 运行脚本：

   ```bash
   python main.py [-h] [-d URL] [-p] [-i] [-f] [-t Int String] [-a] [-n] [-u] [-m] [-c] [-o] [-A]
   ```

### 命令行参数说明

```bash
    -h, --help            显示此帮助消息并退出
    -d URL, --download URL
                          从指定 URL 下载 ROM
    -p, --extract-payload
                          从 zip 文件中提取 payload.bin
    -i, --img             从 payload.bin 中提取指定镜像
    -f, --files           从镜像中提取文件
    -t  --devicetype      修改字典设备类型 (需要2个参数), 0/1 => 不备份/备份, ph/f/p/fp => phone/fold/pad/flip
    -a, --apk             筛选并移动指定有效 APK
    -n, --rename          极速并发重命名 APK 文件为标准格式
    -u, --update-version  比对更新 APK 版本并生成更新包
    -m, --update-name     根据本地应用名字典重命名为中文名
    -c, --clean           删除不需要的中间文件和文件夹
    -o, --get-info        获取系统 build.prop 设备信息
    -A, --all             全自动一键流水线：提取镜像 -> 提取分区 -> 筛选移动 -> 极速重命名 -> 版本比对 -> 应用名重命名
```
