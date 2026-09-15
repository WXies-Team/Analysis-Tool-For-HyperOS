# -*- coding: utf-8 -*-
from config import *  # 从 config.py 模块中导入所有内容
from defs import *  # 从 defs.py 模块中导入所有内容
import argparse
import time


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="EMRA: A high-performance tool to process Android ROM and HyperOS APK files")

    parser.add_argument('-d', '--download', metavar='URL',
                        help='Download ROM from given URL')
    parser.add_argument('-p', '--extract-payload', action='store_true',
                        help='Extract payload.bin from zip files')
    parser.add_argument('-i', '--img', action='store_true',
                        help='Extract img from payload.bin')
    parser.add_argument('-f', '--files', action='store_true',
                        help='Extract files from EROFS img')
    parser.add_argument('-t', '--devicetype', nargs=2, metavar=('Int', 'String'),
                        help='Change the dictionary type (two parameters in total), 0/1 => no backup/backup, ph/f/p/fp => phone/fold/tablet/flip')
    parser.add_argument('-a', '--apk', action='store_true',
                        help='Remove specified APKs and filter')
    parser.add_argument('-n', '--rename', action='store_true',
                        help='Rename APK files to standard format')
    parser.add_argument('-u', '--update-version',
                        action='store_true', help='Update APK versions')
    parser.add_argument('-m', '--update-name',
                        action='store_true', help='Update APK names')
    parser.add_argument('-c', '--clean', action='store_true',
                        help='Delete unnecessary files and folders')
    parser.add_argument('-o', '--get-info', action='store_true',
                        help='Get info from files')
    parser.add_argument('-A', '--all', action='store_true',
                        help='Run full pipeline: extract img -> files -> filter apk -> rename -> update version -> update name')
    return parser.parse_args()


def main():
    args = parse_arguments()

    init_folder()
    exclude_apk, apk_version, apk_code, apk_code_name = init_json()

    total_start = time.time()

    if args.download:
        download_rom(args.download)

    if args.extract_payload:
        # 动态获取最新的 zip 文件列表，避免 import 时静态固化
        extract_payload_bin(get_zip_files())

    if args.all:
        print("====== 启动 HyperOS 自动化全流程处理流水线 ======")
        extract_img()
        extract_files()
        remove_some_apk(exclude_apk)
        rename_apk()
        update_apk_version(apk_version, apk_code, apk_code_name)
        update_apk_name()
        print(f"====== 全流程流水线执行完成，总耗时: {time.time() - total_start:.2f} 秒 ======")
        return

    if args.img:
        extract_img()
    if args.files:
        extract_files()
    if args.devicetype:
        move_json(args.devicetype[0], args.devicetype[1])
    if args.apk:
        remove_some_apk(exclude_apk)
    if args.rename:
        # 动态获取最新的 apk_files 列表，确保 -a -n 连用时不漏文件
        rename_apk()
    if args.update_version:
        update_apk_version(apk_version, apk_code, apk_code_name)
    if args.update_name:
        update_apk_name()
    if args.clean:
        delete_files_and_folders()
    if args.get_info:
        get_info()


if __name__ == "__main__":  # 如果这个脚本文件是被直接运行的
    main()  # 调用main()函数