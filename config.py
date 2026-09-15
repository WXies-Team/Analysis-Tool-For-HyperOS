# -*- coding: utf-8 -*-
import os  # 引入 OS 模块，用于操作文件和目录
import glob  # 引入 glob 模块，用于搜索文件夹中的文件
import shutil
import sys

# 获取当前脚本文件所在目录的绝对路径
src_dir = os.path.dirname(os.path.abspath(__file__))

# 输出与更新目录定义
output_dir = "output_apk"
update_apk_folder = "update_apk"
update_apk_name_folder = "update_name_apk"

# 动态获取 zip 文件与 apk 文件的函数（避免 import 时静态固化导致状态不同步）
def get_zip_files():
    """实时获取当前目录下的所有 .zip 文件"""
    return glob.glob("*.zip")

def get_apk_files():
    """实时获取 output_apk 目录中所有 .apk 文件列表"""
    if not os.path.exists(output_dir):
        return []
    return [f for f in os.listdir(output_dir) if f.endswith(".apk")]

# 保持对旧引用属性的向下兼容（初始状态）
zip_files = get_zip_files()
apk_files = get_apk_files()

# 自适应 CPU 线程数配置
MAX_WORKERS = min(os.cpu_count() or 4, 16)

# 跨平台外部工具智能查找函数
def find_tool(tool_name: str) -> str:
    """
    智能跨平台查找外部命令行工具：
    1. 优先查找 ./tools/<tool_name>.exe (Windows) 或 ./tools/<tool_name>
    2. 其次查找系统 PATH 中的工具
    3. 若都未找到，返回原始名称
    """
    tools_dir = os.path.join(src_dir, "tools")
    exts = [".exe", ""] if sys.platform.startswith("win") else ["", ".exe"]
    for ext in exts:
        candidate = os.path.join(tools_dir, f"{tool_name}{ext}")
        if os.path.isfile(candidate):
            return candidate
    which_path = shutil.which(tool_name)
    if which_path:
        return which_path
    return tool_name

# 定义常量与文件路径
EXCLUDE_APK_PATH = "exclude_apk.txt"
APK_VERSION = "app_version.json"
APK_CODE = "app_code.json"
APK_APP_NAME = "app_name.json"
APK_APP_NAME_PAD = "app_name_pad.json"
# 临时字典，用于存储版本名相同但版本号有所变更的 APK
APK_CODE_NAME = "app_code_name.json"
# 记录 split apk 映射关系的持久化文件（避免跨命令调用时内存丢失）
SPLITS_MAP_FILE = "splits_manifest.json"
# 定义字典类型记录文件
JSON_V = "app_json.txt"

# 相关分区
partitions = [
    "product"
]

# 设备种类识别列表
is_fold = [
    "cetus",
    "zizhan",
    "babylon",
    "goku"
]
is_pad = [
    "spark", 
    "flare", 
    "nabu", 
    "elish", 
    "enuma", 
    "dagu", 
    "yunluo", 
    "pipa", 
    "liuqin", 
    "yudi", 
    "xun", 
    "sheng",
    "dizi",
    "ruan",
    "uke",
    "muyu",
    "jinghu",
    "violin",
    "yupei",
    "piano",
    "taiko",
    "flute",
    "organ",
    "guitar",
    "erhu",
    "turner",
    "yili"
]
is_flip = [
    "ruyi",
    "bixi"
]

# 需要删除的临时文件
files_to_delete = [
    "payload.bin", 
    "product.img", 
    "app_code_name.json",
    SPLITS_MAP_FILE
]
folders_to_delete = [
    "output_apk", 
    "update_apk", 
    "update_name_apk", 
    "product"
]

# 获取设备信息的键值映射
properties = {
    "ro.product.product.name": "设备名",
    "ro.product.build.version.incremental": "软件版本号",
    "ro.product.build.date": "编译时间",
    "ro.product.build.id": "基线",
    "ro.product.build.fingerprint": "指纹"
}
