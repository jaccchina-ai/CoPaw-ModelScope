#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本管理系统
功能：
1. 版本备份：更新前自动备份当前版本
2. 版本注册：记录所有版本信息
3. 一键回滚：退回到任意历史版本
4. 版本对比：查看版本差异
"""

import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

# 目录配置
WORKING_DIR = "/mnt/workspace/working"
SCRIPTS_DIR = os.path.join(WORKING_DIR, "scripts")
VERSIONS_DIR = os.path.join(SCRIPTS_DIR, "versions")
REGISTRY_FILE = os.path.join(SCRIPTS_DIR, "version_registry.json")

# 通用核心文件（适用于所有任务）
COMMON_FILES = [
    "feishu_notifier.py",
    "stockapi_client.py",
]


class VersionManager:
    """版本管理器"""
    
    def __init__(self):
        self._ensure_dirs()
        self.registry = self._load_registry()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(VERSIONS_DIR, exist_ok=True)
    
    def _load_registry(self) -> Dict:
        """加载版本注册表"""
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "versions": {},
            "current": {},
            "created_at": datetime.now().isoformat()
        }
    
    def _save_registry(self):
        """保存版本注册表"""
        self.registry["updated_at"] = datetime.now().isoformat()
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)
    
    def _calc_file_hash(self, filepath: str) -> str:
        """计算文件MD5哈希"""
        if not os.path.exists(filepath):
            return ""
        
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _copy_file(self, src: str, dst: str):
        """复制文件"""
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    
    def backup_version(self, module_name: str, version: str, description: str = "") -> Dict:
        """
        备份当前版本（通用版，适用于所有任务）
        
        Args:
            module_name: 模块名称（如 T01_evening_analysis, T02_xxx）
            version: 版本号（如 v1.0.0）
            description: 版本描述
        
        Returns:
            dict: 备份结果
        """
        result = {
            "success": False,
            "module": module_name,
            "version": version,
            "files": [],
            "errors": []
        }
        
        # 创建版本目录
        version_dir = os.path.join(VERSIONS_DIR, module_name, version)
        os.makedirs(version_dir, exist_ok=True)
        
        # 获取模块前缀（如 T01, T02）
        module_prefix = module_name.split('_')[0] if '_' in module_name else module_name
        
        # 备份策略：
        # 1. 备份与模块名匹配的py文件
        # 2. 备份通用核心文件
        backed_up = set()
        
        for filename in os.listdir(SCRIPTS_DIR):
            if not filename.endswith('.py'):
                continue
            
            src = os.path.join(SCRIPTS_DIR, filename)
            
            # 判断是否需要备份
            should_backup = False
            
            # 策略1: 文件名包含模块前缀（如 T01_xxx.py）
            if module_prefix in filename:
                should_backup = True
            
            # 策略2: 文件名包含模块名的主要部分（如 evening_analysis）
            module_main = '_'.join(module_name.split('_')[1:]) if '_' in module_name else ''
            if module_main and module_main in filename:
                should_backup = True
            
            # 策略3: 通用核心文件
            if filename in COMMON_FILES:
                should_backup = True
            
            if should_backup and filename not in backed_up:
                dst = os.path.join(version_dir, filename)
                try:
                    self._copy_file(src, dst)
                    file_hash = self._calc_file_hash(src)
                    result["files"].append({
                        "name": filename,
                        "hash": file_hash,
                        "size": os.path.getsize(src)
                    })
                    backed_up.add(filename)
                except Exception as e:
                    result["errors"].append(f"{filename}: {str(e)}")
        
        # 更新注册表
        version_key = f"{module_name}_{version}"
        self.registry["versions"][version_key] = {
            "module": module_name,
            "version": version,
            "description": description,
            "backup_time": datetime.now().isoformat(),
            "files": result["files"],
            "path": version_dir
        }
        
        # 更新当前版本
        if module_name not in self.registry["current"]:
            self.registry["current"][module_name] = {}
        self.registry["current"][module_name]["version"] = version
        self.registry["current"][module_name]["path"] = version_dir
        
        self._save_registry()
        
        result["success"] = len(result["errors"]) == 0 and len(result["files"]) > 0
        return result
    
    def restore_version(self, module_name: str, version: str) -> Dict:
        """
        恢复到指定版本（回滚）
        
        Args:
            module_name: 模块名称
            version: 版本号
        
        Returns:
            dict: 恢复结果
        """
        result = {
            "success": False,
            "module": module_name,
            "version": version,
            "restored_files": [],
            "errors": []
        }
        
        version_key = f"{module_name}_{version}"
        version_info = self.registry["versions"].get(version_key)
        
        if not version_info:
            result["errors"].append(f"版本 {version_key} 不存在")
            return result
        
        version_dir = version_info.get("path", "")
        if not os.path.exists(version_dir):
            result["errors"].append(f"版本目录 {version_dir} 不存在")
            return result
        
        # 先备份当前版本
        current_version = self.registry["current"].get(module_name, {}).get("version", "current")
        if current_version != version:
            print(f"备份当前版本: {current_version} -> backup_before_restore")
            self.backup_version(module_name, f"{current_version}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "回滚前自动备份")
        
        # 恢复文件
        for file_info in version_info.get("files", []):
            filename = file_info["name"]
            src = os.path.join(version_dir, filename)
            dst = os.path.join(SCRIPTS_DIR, filename)
            
            try:
                if os.path.exists(src):
                    self._copy_file(src, dst)
                    result["restored_files"].append(filename)
                else:
                    result["errors"].append(f"{filename}: 源文件不存在")
            except Exception as e:
                result["errors"].append(f"{filename}: {str(e)}")
        
        # 更新当前版本
        if module_name in self.registry["current"]:
            self.registry["current"][module_name]["version"] = version
            self.registry["current"][module_name]["path"] = version_dir
            self.registry["current"][module_name]["restored_at"] = datetime.now().isoformat()
        
        self._save_registry()
        
        result["success"] = len(result["restored_files"]) > 0
        return result
    
    def list_versions(self, module_name: str = None) -> List[Dict]:
        """
        列出所有版本
        
        Args:
            module_name: 模块名称（可选，不传则列出所有）
        
        Returns:
            list: 版本列表
        """
        versions = []
        
        for key, info in self.registry["versions"].items():
            if module_name is None or info.get("module") == module_name:
                versions.append({
                    "key": key,
                    "module": info.get("module"),
                    "version": info.get("version"),
                    "description": info.get("description", ""),
                    "backup_time": info.get("backup_time"),
                    "file_count": len(info.get("files", []))
                })
        
        # 按备份时间排序
        versions.sort(key=lambda x: x.get("backup_time", ""), reverse=True)
        
        return versions
    
    def get_current_version(self, module_name: str) -> Optional[Dict]:
        """获取当前版本信息"""
        current = self.registry["current"].get(module_name)
        if current:
            version_key = f"{module_name}_{current.get('version')}"
            return self.registry["versions"].get(version_key)
        return None
    
    def verify_version(self, module_name: str, version: str) -> Dict:
        """
        验证版本完整性
        
        Args:
            module_name: 模块名称
            version: 版本号
        
        Returns:
            dict: 验证结果
        """
        result = {
            "valid": True,
            "missing_files": [],
            "hash_mismatch": []
        }
        
        version_key = f"{module_name}_{version}"
        version_info = self.registry["versions"].get(version_key)
        
        if not version_info:
            result["valid"] = False
            result["error"] = "版本不存在"
            return result
        
        version_dir = version_info.get("path", "")
        
        for file_info in version_info.get("files", []):
            filename = file_info["name"]
            filepath = os.path.join(version_dir, filename)
            
            if not os.path.exists(filepath):
                result["missing_files"].append(filename)
                result["valid"] = False
            else:
                # 验证哈希
                current_hash = self._calc_file_hash(filepath)
                if current_hash != file_info.get("hash"):
                    result["hash_mismatch"].append(filename)
        
        return result


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='版本管理系统')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # backup 命令
    backup_parser = subparsers.add_parser('backup', help='备份当前版本')
    backup_parser.add_argument('module', help='模块名称')
    backup_parser.add_argument('version', help='版本号')
    backup_parser.add_argument('--desc', default='', help='版本描述')
    
    # restore 命令
    restore_parser = subparsers.add_parser('restore', help='恢复到指定版本')
    restore_parser.add_argument('module', help='模块名称')
    restore_parser.add_argument('version', help='版本号')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有版本')
    list_parser.add_argument('--module', help='模块名称（可选）')
    
    # current 命令
    current_parser = subparsers.add_parser('current', help='查看当前版本')
    current_parser.add_argument('module', help='模块名称')
    
    # verify 命令
    verify_parser = subparsers.add_parser('verify', help='验证版本完整性')
    verify_parser.add_argument('module', help='模块名称')
    verify_parser.add_argument('version', help='版本号')
    
    args = parser.parse_args()
    
    vm = VersionManager()
    
    if args.command == 'backup':
        result = vm.backup_version(args.module, args.version, args.desc)
        print(f"\n备份结果: {'成功' if result['success'] else '失败'}")
        print(f"备份文件: {len(result['files'])} 个")
        if result['errors']:
            print(f"错误: {result['errors']}")
    
    elif args.command == 'restore':
        result = vm.restore_version(args.module, args.version)
        print(f"\n恢复结果: {'成功' if result['success'] else '失败'}")
        print(f"恢复文件: {len(result['restored_files'])} 个")
        if result['errors']:
            print(f"错误: {result['errors']}")
    
    elif args.command == 'list':
        versions = vm.list_versions(args.module)
        print(f"\n共 {len(versions)} 个版本:")
        for v in versions:
            print(f"  {v['key']}: {v['description']} ({v['backup_time']})")
    
    elif args.command == 'current':
        current = vm.get_current_version(args.module)
        if current:
            print(f"\n当前版本: {current.get('version')}")
            print(f"备份时间: {current.get('backup_time')}")
        else:
            print("\n未找到当前版本")
    
    elif args.command == 'verify':
        result = vm.verify_version(args.module, args.version)
        print(f"\n验证结果: {'通过' if result['valid'] else '失败'}")
        if result.get('missing_files'):
            print(f"缺失文件: {result['missing_files']}")
        if result.get('hash_mismatch'):
            print(f"哈希不匹配: {result['hash_mismatch']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
