# -*- coding: utf-8 -*-
from config import *  # 导入 config.py 中定义的全局变量与配置
import fnmatch  # 导入 fnmatch 模块，用于文件名匹配
import json  # 导入 json 模块，用于读写 JSON 格式的数据
import os
import re
import shutil  # 导入 shutil 模块，用于复制、移动、删除文件和目录
import subprocess  # 导入 subprocess 模块，用于执行系统命令
import sys
import time
import zipfile  # 导入 zipfile 模块，用于打包 APK 集合
from concurrent.futures import ThreadPoolExecutor  # 高并发解析 APK
from axml_parser import parse_apk_metadata  # 导入零依赖极速 AXML 解析器

# 记录每个包名对应的 split APK 路径
_splits_by_package = {}

# 扫描时需要主动剪枝跳过的非目标目录
PRUNE_DIRS = {
    ".git",
    ".github",
    "tools",
    "phone",
    "fold",
    "pad",
    "flip",
    output_dir,
    update_apk_folder,
    update_apk_name_folder,
    "__pycache__",
}

# 设备类型字典映射：类型参数 -> (目录名, 标识名)
DEVICE_TYPE_MAP = {
    "ph": ("phone", "Phone"),
    "f": ("fold", "Fold"),
    "p": ("pad", "Pad"),
    "fp": ("flip", "Flip"),
}


def sanitize_filename(name: str) -> str:
    """清洗文件名中的非法字符（特别针对 Windows 系统：/ \\ : * ? \" < > |）"""
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    return cleaned if cleaned else "app"


def _save_splits_manifest():
    """将 splits 映射持久化保存到本地文件，确保分步执行命令行时状态不丢失"""
    try:
        with open(SPLITS_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(_splits_by_package, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 无法保存 splits 映射缓存: {e}")


def _load_splits_manifest():
    """从本地持久化文件恢复 splits 映射"""
    global _splits_by_package
    if os.path.exists(SPLITS_MAP_FILE):
        try:
            with open(SPLITS_MAP_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    _splits_by_package.update(loaded)
        except Exception:
            pass


def _process_apk_for_rename(apk_path: str):
    """
    解析单个 APK 并重命名为 包名^版本名^版本号.apk。
    采用三级解析策略：内置极速 AXML 解析 -> aapt2 命令行 -> androguard 兜底
    """
    if not os.path.isfile(apk_path):
        return None

    package_name = ""
    version_name = ""
    version_code = 0
    is_split = False

    # 1. 优先使用极速内置 AXML 解析（几毫秒，零外部依赖）
    try:
        package_name, version_name, version_code, is_split = parse_apk_metadata(apk_path)
    except Exception as axml_err:
        # 2. 如果内置解析遇到特殊加固/混淆 APK，尝试 fallback 到 androguard（若有安装）
        try:
            from androguard.core.apk import APK
            apk = APK(apk_path)
            manifest = apk.get_android_manifest_xml()
            if manifest is not None and manifest.get(APK._ns("split")):
                is_split = True
            package_name = apk.get_package() or ""
            version_name = apk.get_androidversion_name() or ""
            version_code = int(apk.get_androidversion_code() or 0)
        except Exception as andro_err:
            return f"[跳过] 无法解析 {os.path.basename(apk_path)}: {axml_err} (Fallback 异常: {andro_err})"

    if not package_name:
        return f"[跳过] {os.path.basename(apk_path)} 未能获取到有效的包名"

    if is_split:
        return ("split", package_name, apk_path)

    # 构造标准重命名文件名
    new_name = f"{package_name}^{version_name}^{version_code}.apk"
    dst = os.path.join(os.path.dirname(apk_path), new_name)
    if os.path.abspath(apk_path) != os.path.abspath(dst):
        try:
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(apk_path, dst)
        except Exception as e:
            return f"[错误] 重命名 {os.path.basename(apk_path)} 失败: {e}"

    return None


def move_json(backup, type_name):
    """切换与同步设备字典库"""
    if type_name not in DEVICE_TYPE_MAP:
        print(f"[错误] 未知的设备类型参数 '{type_name}'，支持的值: ph/f/p/fp")
        return

    folder_name, display_name = DEVICE_TYPE_MAP[type_name]

    # 获取当前字典类型
    current_line = "Phone"
    if os.path.exists(JSON_V):
        try:
            with open(JSON_V, "r", encoding="utf-8") as f:
                current_line = f.readline().strip()
                print("当前字典列表为:", current_line)
        except Exception as e:
            print(f"[警告] 读取 {JSON_V} 失败: {e}")

    # 同步备份现有字典库
    if int(backup) == 1:
        print(f"正在同步到 {current_line} 字典库目录")
        # 查找当前类型对应的目录
        src_folder = None
        for k, (fld, disp) in DEVICE_TYPE_MAP.items():
            if disp.lower() == current_line.lower():
                src_folder = fld
                break
        if not src_folder:
            src_folder = "phone"

        for json_file in ["app_version.json", "app_code.json"]:
            src_path = os.path.join(".", json_file)
            dst_path = os.path.join(f"./{src_folder}", json_file)
            if os.path.exists(src_path):
                shutil.move(src_path, dst_path)
        print(f"字典库已同步到 {src_folder} 目录，正在切换")
    else:
        print("正在覆盖字典库目录（不备份）")

    # 复制目标字典库到根目录
    for json_file in ["app_version.json", "app_code.json"]:
        src_path = os.path.join(f"./{folder_name}", json_file)
        dst_path = os.path.join(".", json_file)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)

    # 更新标记文件
    try:
        with open(JSON_V, "w", encoding="utf-8") as file:
            file.write(display_name)
        print(f"字典库已变更为 {display_name}")
    except Exception as e:
        print(f"[错误] 写入 {JSON_V} 失败: {e}")


def init_folder():
    """检查并创建所需的运行文件夹"""
    for fld in [output_dir, update_apk_folder, update_apk_name_folder]:
        os.makedirs(fld, exist_ok=True)

    if not os.path.exists(APK_CODE) or not os.path.exists(APK_VERSION):
        print("检测到根目录下没有字典库，正在初始化字典库为 Phone")
        move_json(0, "ph")
        print("如有更换字典库需要，请使用 -t 0/1 ph/f/p/fp 命令进行切换")


def init_json():
    """初始化排除 APK 列表和本地版本字典"""
    exclude_apk = []
    apk_version = {}
    apk_code = {}
    apk_code_name = {}

    # 查询 APK 排除列表
    if os.path.exists(EXCLUDE_APK_PATH):
        try:
            with open(EXCLUDE_APK_PATH, "r", encoding="utf-8") as f:
                exclude_apk = [line.strip() for line in f if line.strip()]
        except Exception:
            with open(EXCLUDE_APK_PATH, "r", errors="ignore") as f:
                exclude_apk = [line.strip() for line in f if line.strip()]

    # 查询本地字典版本名
    if os.path.exists(APK_VERSION):
        try:
            with open(APK_VERSION, "r", encoding="utf-8") as f:
                apk_version = json.load(f)
        except Exception as e:
            print(f"[警告] 读取 {APK_VERSION} 失败: {e}")

    # 查询本地字典版本号
    if os.path.exists(APK_CODE):
        try:
            with open(APK_CODE, "r", encoding="utf-8") as f:
                apk_code = json.load(f)
        except Exception as e:
            print(f"[警告] 读取 {APK_CODE} 失败: {e}")

    return exclude_apk, apk_version, apk_code, apk_code_name


def download_rom(url):
    """从给定的 URL 下载 ROM，支持断点续传和多连接并发"""
    tool = find_tool("aria2c")
    cmd = [tool, "-x16", "-s16", "-k1M", "-c", url]
    print(f"正在启动下载: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(f"[错误] 未找到 aria2c 下载工具，请确保已安装 aria2c 并加入 PATH，或放置于 ./tools/ 目录下。")
    except subprocess.CalledProcessError as e:
        print(f"[错误] 下载失败，错误代码: {e.returncode}")


def extract_payload_bin(zip_files=None):
    """从 ZIP 文件中提取 payload.bin 文件"""
    if zip_files is None:
        zip_files = get_zip_files()

    if not zip_files:
        print("未检测到 .zip 文件")
        return

    tool = find_tool("7z")
    for f in zip_files:
        try:
            cmd = [tool, "x", "-y", f, "payload.bin"]
            print(f"正在从 {f} 提取 payload.bin...")
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            print(f"[错误] 未找到 7z 解包工具，请确保已安装 7-Zip 并配置 PATH，或将 7z.exe 放置于 ./tools/。")
            break
        except Exception as e:
            print(f"提取 payload.bin 异常: {e}")


def extract_img():
    """从 payload.bin 文件中提取指定镜像文件"""
    tool = find_tool("payload-dumper-go")
    partition_string = ",".join(partitions)
    cmd = [tool, "-c", str(MAX_WORKERS), "-o", "./", "-p", partition_string, "payload.bin"]
    print(f"正在提取镜像: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(f"[错误] 未找到 payload-dumper-go，请前往 Release 下载并将工具放置于 ./tools/ 目录中。")
    except Exception as e:
        print(f"提取镜像异常: {e}")


def normalize_product_name(name):
    """去除小米 product name 中的 miproduct_/miproduct- 前缀"""
    for prefix in ("miproduct_", "miproduct-"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def extract_files():
    """从镜像中提取文件，并自动识别设备类型"""
    tool = find_tool("extract.erofs")
    try:
        # 提取镜像文件中的文件
        for image in partitions:
            img_file = image + ".img"
            if not os.path.exists(img_file):
                print(f"[提示] 未找到 {img_file}，跳过提取")
                continue
            cmd = [tool, "-i", img_file, "-x", f"-T{MAX_WORKERS}"]
            print(f"正在解包 {img_file}...")
            subprocess.run(cmd, check=True)

        # 搜索 build.prop 识别设备类型
        build_prop_paths = [
            "./product/etc/build.prop",
            "./system/etc/build.prop",
            "./build.prop",
        ]
        found = False
        for bp in build_prop_paths:
            if os.path.isfile(bp):
                found = True
                with open(bp, "r", encoding="utf-8", errors="ignore") as file:
                    for line in file:
                        if line.startswith("ro.product.product.name"):
                            device_name = normalize_product_name(line.split("=")[1].strip())
                            print(f"\n设备名: {device_name}")

                            if device_name in is_fold:
                                print("检测到包设备为 Fold，建议使用: -t 0/1 f 切换字典库")
                            elif device_name in is_pad:
                                print("检测到包设备为 Pad，建议使用: -t 0/1 p 切换字典库")
                            elif device_name in is_flip:
                                print("检测到包设备为 Flip，建议使用: -t 0/1 fp 切换字典库")
                            else:
                                print("检测到包设备为 Phone，建议使用: -t 0/1 ph 切换字典库")
                            break
                break
        if not found:
            print("未找到 build.prop 文件")
    except FileNotFoundError:
        print(f"[错误] 未找到 extract.erofs，请确保已下载并将 extract.erofs(.exe) 放置于 ./tools/ 目录下。")
    except Exception as e:
        print(f"解包镜像异常: {e}")


def remove_some_apk(exclude_apk):
    """
    高效扫描并过滤 APK：
    1. 定向扫描解包分区目录，避免对根目录做无意义的全盘深搜与 .git 遍历
    2. 将排除表转换为 Set，单次就地过滤，直接跳过 overlay 与 _sys 文件，避免二次 I/O 搬运
    """
    t0 = time.time()
    exclude_set = set(exclude_apk)
    os.makedirs(output_dir, exist_ok=True)

    # 确定优先扫描的目标目录
    scan_targets = []
    for part in partitions:
        if os.path.isdir(part):
            scan_targets.append(part)

    # 如果分区目录不存在（用户自定义了解包目录），则扫描当前目录并做智能剪枝
    if not scan_targets:
        scan_targets = ["."]

    moved_count = 0
    skipped_count = 0

    print(f"正在扫描并筛选 APK 文件 (扫描范围: {scan_targets})...")
    for target in scan_targets:
        for root, dirs, files in os.walk(target):
            # 智能剪枝：如果在根目录下，过滤掉无关的系统和代码文件夹
            if target == ".":
                dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]

            for file in files:
                if not file.lower().endswith(".apk"):
                    continue

                lower_name = file.lower()
                # 就地一次性过滤规则：排除名单 或 包含 overlay / _sys
                if file in exclude_set or "overlay" in lower_name or "_sys" in lower_name:
                    skipped_count += 1
                    continue

                src = os.path.join(root, file)
                dst = os.path.join(output_dir, file)

                # 如果同名文件已存在且不是同一文件，重命名保存
                if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
                    base, ext = os.path.splitext(file)
                    dst = os.path.join(output_dir, f"{base}_{moved_count}{ext}")

                try:
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.move(src, dst)
                        moved_count += 1
                except Exception as e:
                    print(f"移动文件 {src} 异常: {e}")

    elapsed = time.time() - t0
    print(f"APK 筛选完成: 移动有效应用 {moved_count} 个，过滤排除 {skipped_count} 个，耗时 {elapsed:.2f} 秒\n")


def rename_apk(apk_files=None):
    """
    极速并发重命名 output_apk 中的所有 APK 文件。
    使用内置纯 Python AXML 解析器与多线程池，处理几百个 APK 仅需几秒。
    """
    global _splits_by_package
    _splits_by_package = {}

    # 动态获取最新的 APK 文件列表
    if apk_files is None:
        apk_files = get_apk_files()
    else:
        # 兼容外部传入文件名列表或带路径的列表
        apk_files = [os.path.basename(f) for f in apk_files if f.endswith(".apk")]

    if not apk_files:
        print(f"[提示] {output_dir} 目录中未找到任何 .apk 文件，请先执行 -a 提取筛选")
        return

    apk_paths = [os.path.join(output_dir, f) for f in apk_files]
    total = len(apk_paths)
    print(f"开始极速解析并重命名 {total} 个 APK 文件...")

    t0 = time.time()
    # 纯内存解压与 AXML 读取是 I/O 与微量 CPU 密集，线程池开销远小于多进程
    workers = min(32, (os.cpu_count() or 4) * 2)
    split_count = 0
    renamed_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(_process_apk_for_rename, apk_paths):
            if isinstance(result, tuple) and result and result[0] == "split":
                _, package, path = result
                _splits_by_package.setdefault(package, []).append(path)
                split_count += 1
            elif result:
                print(result)
            else:
                renamed_count += 1

    # 持久化保存 splits 关系，防止分步运行命令行时丢失
    _save_splits_manifest()

    elapsed = time.time() - t0
    print(f"重命名完成: 成功解析重命名 {renamed_count} 个，发现 split 分包 {split_count} 个，耗时 {elapsed:.2f} 秒\n")


def _deliver_update(package, apk_file, folder):
    """复制更新的 APK 及其同包名 splits，并打包成 .apks 文件"""
    os.makedirs(folder, exist_ok=True)
    src = os.path.join(output_dir, apk_file)
    shutil.copy2(src, os.path.join(folder, apk_file))
    print(f"已将 {apk_file} 复制到 {folder} 文件夹")

    # 尝试从内存或持久化缓存中加载 splits
    splits = _splits_by_package.get(package, [])
    if not splits and os.path.exists(SPLITS_MAP_FILE):
        _load_splits_manifest()
        splits = _splits_by_package.get(package, [])

    for split_path in splits:
        if os.path.exists(split_path):
            shutil.copy2(split_path, os.path.join(folder, os.path.basename(split_path)))

    set_name = os.path.splitext(apk_file)[0] + ".apks"
    apks_path = os.path.join(folder, set_name)
    with zipfile.ZipFile(apks_path, "w", zipfile.ZIP_STORED) as zf:
        zf.write(src, "base.apk")
        for split_path in splits:
            if os.path.exists(split_path):
                zf.write(split_path, os.path.basename(split_path))
    print(f"已将 {set_name} 打包到 {folder} 文件夹\n")


def update_apk_version(apk_version, apk_code, apk_code_name):
    """遍历 output_apk 下的标准格式 APK，对比版本并更新本地词典"""
    _load_splits_manifest()
    apk_files = get_apk_files()

    if not apk_files:
        print(f"[提示] {output_dir} 目录中未找到任何 .apk 文件")
        return

    update_count = 0
    new_count = 0

    for apk_file in apk_files:
        try:
            parts = os.path.splitext(apk_file)[0].split("^")
            if len(parts) != 3:
                continue
            x, y, z = parts
            z_int = int(z)

            if x in apk_code:
                if apk_code[x] < z_int:
                    print(f"更新 {x}：{apk_code[x]} -> {z}")
                    apk_version[x] = y
                    apk_code[x] = z_int
                    apk_code_name[x] = z_int
                    _deliver_update(x, apk_file, update_apk_folder)
                    update_count += 1
                elif apk_code[x] == z_int:
                    if apk_version.get(x) != y:
                        print(f"疑似更新 {x}：{apk_version.get(x)} -> {y}")
                        _deliver_update(x, apk_file, update_apk_name_folder)
                        update_count += 1
            else:
                print(f"添加新应用 {x}: {y} ({z})")
                apk_version[x] = y
                apk_code[x] = z_int
                new_count += 1
        except Exception as e:
            print(f"处理 {apk_file} 异常: {e}")
            continue

    # 规范化保存 JSON 字典（统一 UTF-8 编码、缩进与中文保留）
    with open(APK_VERSION, "w", encoding="utf-8") as f:
        json.dump(apk_version, f, ensure_ascii=False, indent=2)
    with open(APK_CODE, "w", encoding="utf-8") as f:
        json.dump(apk_code, f, ensure_ascii=False, indent=2)
    with open(APK_CODE_NAME, "w", encoding="utf-8") as f:
        json.dump(apk_code_name, f, ensure_ascii=False, indent=2)

    print(f"版本对比完成: 发现更新 {update_count} 个，新增应用 {new_count} 个\n")


def update_apk_name():
    """根据应用中文名字典重命名 APK 文件，并消除冗余分支与 Windows 非法字符"""
    current_line = "Phone"
    if os.path.exists(JSON_V):
        try:
            with open(JSON_V, "r", encoding="utf-8") as file:
                current_line = file.readline().strip()
        except Exception:
            pass

    # 根据字典类别读取应用名对照表
    name_file = APK_APP_NAME_PAD if current_line.lower() == "pad" else APK_APP_NAME
    apk_name = {}
    if os.path.exists(name_file):
        try:
            with open(name_file, "r", encoding="utf-8") as f:
                apk_name = json.load(f)
        except Exception as e:
            print(f"[警告] 读取 {name_file} 失败: {e}")

    def rename_files_in_folder(folder, name_dict):
        if not os.path.exists(folder):
            return
        for apk_file in os.listdir(folder):
            if not apk_file.endswith(".apk"):
                continue
            parts = os.path.splitext(apk_file)[0].split("^")
            if len(parts) != 3:
                continue
            pkg, ver_name, ver_code = parts
            if pkg in name_dict:
                # 获取清洗后的合法文件名，避免 Windows 下特殊字符引发 OSError
                clean_name = sanitize_filename(name_dict[pkg])
                new_file = f"{clean_name}_{ver_name}({ver_code}).apk"
                src_path = os.path.join(folder, apk_file)
                dst_path = os.path.join(folder, new_file)
                try:
                    if os.path.exists(dst_path):
                        os.remove(dst_path)
                    os.rename(src_path, dst_path)
                    print(f"重命名: {apk_file} -> {new_file}")
                except Exception as e:
                    print(f"[错误] 重命名 {apk_file} 失败: {e}")

    # 重命名各个输出目录中的 APK 文件
    for fld in [output_dir, update_apk_folder, update_apk_name_folder]:
        rename_files_in_folder(fld, apk_name)


def delete_files_and_folders():
    """删除临时文件和解包生成的文件夹"""
    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"{file} 删除成功")
            except OSError as e:
                print(f"无法删除 {file}: {e}")
        else:
            print(f"{file} 不存在")

    for folder in folders_to_delete:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"{folder} 删除成功")
                except OSError as e:
                    print(f"无法删除 {folder}: {e}")
            else:
                print(f"{folder} 不是文件夹")
        else:
            print(f"{folder} 不存在")


def get_info():
    """从 build.prop 获取设备编译与系统信息"""
    build_prop_candidates = [
        "./product/etc/build.prop",
        "./system/etc/build.prop",
        "./build.prop",
    ]
    prop_path = None
    for bp in build_prop_candidates:
        if os.path.isfile(bp):
            prop_path = bp
            break

    if not prop_path:
        print("未找到 build.prop，请在执行 -f 指令解包后再执行本参数")
        return

    try:
        with open(prop_path, "r", encoding="utf-8", errors="ignore") as file:
            lines = file.readlines()
            for key, label in properties.items():
                for line in lines:
                    if line.startswith(key):
                        value = line.split("=")[1].strip()
                        if key == "ro.product.product.name":
                            value = normalize_product_name(value)
                        print(f"{label}: {value}")
                        break
    except Exception as e:
        print(f"读取属性信息异常: {e}")
