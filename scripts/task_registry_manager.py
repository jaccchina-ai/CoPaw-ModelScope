#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务注册表管理器
用于管理多个任务的注册信息
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

REGISTRY_FILE = "/mnt/workspace/working/task_registry.json"


class TaskRegistryManager:
    """任务注册表管理器"""

    def __init__(self, registry_file: str = REGISTRY_FILE):
        self.registry_file = registry_file
        self.registry = self.load_registry()

    def load_registry(self) -> Dict:
        """加载任务注册表"""
        if not os.path.exists(self.registry_file):
            return self.create_empty_registry()

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载注册表失败: {e}")
            return self.create_empty_registry()

    def save_registry(self):
        """保存任务注册表"""
        try:
            self.registry['updated_at'] = datetime.now().isoformat() + 'Z'
            self.update_statistics()

            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)

            print(f"注册表已保存到: {self.registry_file}")
        except Exception as e:
            print(f"保存注册表失败: {e}")

    def create_empty_registry(self) -> Dict:
        """创建空的注册表"""
        return {
            "registry_version": "1.0.0",
            "created_at": datetime.now().isoformat() + 'Z',
            "updated_at": datetime.now().isoformat() + 'Z',
            "tasks": [],
            "statistics": {
                "total_tasks": 0,
                "active_tasks": 0,
                "paused_tasks": 0,
                "inactive_tasks": 0,
                "tasks_by_category": {},
                "tasks_by_status": {}
            }
        }

    def update_statistics(self):
        """更新统计信息"""
        tasks = self.registry.get('tasks', [])

        # 基础统计
        self.registry['statistics']['total_tasks'] = len(tasks)
        self.registry['statistics']['active_tasks'] = len([t for t in tasks if t.get('status') == 'active'])
        self.registry['statistics']['paused_tasks'] = len([t for t in tasks if t.get('status') == 'paused'])
        self.registry['statistics']['inactive_tasks'] = len([t for t in tasks if t.get('status') == 'inactive'])

        # 按分类统计
        category_count = {}
        for task in tasks:
            category = task.get('category', '未分类')
            category_count[category] = category_count.get(category, 0) + 1
        self.registry['statistics']['tasks_by_category'] = category_count

        # 按状态统计
        status_count = {}
        for task in tasks:
            status = task.get('status', 'unknown')
            status_count[status] = status_count.get(status, 0) + 1
        self.registry['statistics']['tasks_by_status'] = status_count

    def add_task(self, task: Dict) -> bool:
        """添加任务"""
        # 检查任务ID是否已存在
        task_id = task.get('id')
        if self.get_task(task_id):
            print(f"任务ID {task_id} 已存在，无法添加")
            return False

        # 设置创建时间和更新时间
        if 'created_at' not in task:
            task['created_at'] = datetime.now().isoformat() + 'Z'
        if 'updated_at' not in task:
            task['updated_at'] = datetime.now().isoformat() + 'Z'

        # 添加到注册表
        self.registry['tasks'].append(task)
        self.save_registry()

        print(f"任务 {task_id} ({task.get('name')}) 已添加")
        return True

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务"""
        for task in self.registry.get('tasks', []):
            if task.get('id') == task_id:
                return task
        return None

    def update_task(self, task_id: str, updates: Dict) -> bool:
        """更新任务"""
        task = self.get_task(task_id)
        if not task:
            print(f"任务ID {task_id} 不存在")
            return False

        # 更新任务字段
        task.update(updates)
        task['updated_at'] = datetime.now().isoformat() + 'Z'

        self.save_registry()
        print(f"任务 {task_id} 已更新")
        return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        task = self.get_task(task_id)
        if not task:
            print(f"任务ID {task_id} 不存在")
            return False

        self.registry['tasks'].remove(task)
        self.save_registry()

        print(f"任务 {task_id} ({task.get('name')}) 已删除")
        return True

    def list_tasks(self, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        """列出任务"""
        tasks = self.registry.get('tasks', [])

        # 筛选状态
        if status:
            tasks = [t for t in tasks if t.get('status') == status]

        # 筛选分类
        if category:
            tasks = [t for t in tasks if t.get('category') == category]

        return tasks

    def print_task_list(self, status: Optional[str] = None, category: Optional[str] = None):
        """打印任务列表"""
        tasks = self.list_tasks(status=status, category=category)

        if not tasks:
            print("没有找到任务")
            return

        print("=" * 80)
        print(f"任务列表 ({len(tasks)} 个任务)")
        print("=" * 80)
        print(f"{'ID':<8} {'名称':<20} {'版本':<10} {'状态':<10} {'分类':<15} {'优先级':<10}")
        print("-" * 80)

        for task in tasks:
            print(f"{task['id']:<8} {task['name']:<20} {task['version']:<10} "
                  f"{task['status']:<10} {task.get('category', 'N/A'):<15} {task.get('priority', 'normal'):<10}")

        print("=" * 80)

    def print_task_details(self, task_id: str):
        """打印任务详情"""
        task = self.get_task(task_id)
        if not task:
            print(f"任务ID {task_id} 不存在")
            return

        print("=" * 80)
        print(f"任务详情: {task['id']} - {task['name']}")
        print("=" * 80)
        print(f"版本: {task['version']}")
        print(f"状态: {task['status']}")
        print(f"分类: {task.get('category', 'N/A')}")
        print(f"优先级: {task.get('priority', 'normal')}")
        print(f"作者: {task.get('author', 'N/A')}")
        print(f"创建时间: {task['created_at']}")
        print(f"更新时间: {task['updated_at']}")
        print(f"\n描述:")
        print(f"  {task.get('description', 'N/A')}")

        if 'schedule' in task:
            print(f"\n调度配置:")
            schedule = task['schedule']
            if 'evening_job' in schedule:
                job = schedule['evening_job']
                print(f"  晚间任务: {job.get('time')} - {job.get('description')}")
                print(f"    脚本: {job.get('script')}")
                print(f"    状态: {'启用' if job.get('enabled') else '禁用'}")
            if 'morning_job' in schedule:
                job = schedule['morning_job']
                print(f"  早盘任务: {job.get('time')} - {job.get('description')}")
                print(f"    脚本: {job.get('script')}")
                print(f"    状态: {'启用' if job.get('enabled') else '禁用'}")

        if 'data_sources' in task:
            print(f"\n数据源:")
            for ds in task['data_sources']:
                print(f"  - {ds.get('name', 'N/A')}: {ds.get('url', 'N/A')}")

        if 'files' in task:
            print(f"\n相关文件:")
            files = task['files']
            print(f"  文档: {files.get('doc', 'N/A')}")
            print(f"  数据目录: {files.get('data_dir', 'N/A')}")
            print(f"  脚本:")
            for script in files.get('scripts', []):
                print(f"    - {script}")

        if 'notes' in task and task['notes']:
            print(f"\n备注:")
            for note in task['notes']:
                print(f"  - {note}")

        if 'changelog' in task and task['changelog']:
            print(f"\n变更日志:")
            for log in task['changelog']:
                print(f"  v{log['version']} ({log['date']}):")
                for change in log['changes']:
                    print(f"    - {change}")

        print("=" * 80)

    def add_changelog(self, task_id: str, version: str, changes: List[str]):
        """添加变更日志"""
        task = self.get_task(task_id)
        if not task:
            print(f"任务ID {task_id} 不存在")
            return False

        # 更新版本
        task['version'] = version

        # 添加变更日志
        if 'changelog' not in task:
            task['changelog'] = []

        task['changelog'].append({
            "version": version,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "changes": changes
        })

        task['updated_at'] = datetime.now().isoformat() + 'Z'
        self.save_registry()

        print(f"任务 {task_id} 变更日志已添加 (v{version})")
        return True


def main():
    """主函数 - 命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  查看所有任务: python task_registry_manager.py list")
        print("  查看任务详情: python task_registry_manager.py show <task_id>")
        print("  添加任务: python task_registry_manager.py add <json_file>")
        print("  更新任务: python task_registry_manager.py update <task_id>")
        print("  删除任务: python task_registry_manager.py delete <task_id>")
        print("  添加变更日志: python task_registry_manager.py changelog <task_id> <version>")
        sys.exit(1)

    manager = TaskRegistryManager()
    command = sys.argv[1]

    if command == "list":
        status = sys.argv[3] if len(sys.argv) > 3 else None
        category = sys.argv[5] if len(sys.argv) > 5 else None
        manager.print_task_list(status=status, category=category)

    elif command == "show":
        task_id = sys.argv[2]
        manager.print_task_details(task_id)

    elif command == "add":
        json_file = sys.argv[2]
        if not os.path.exists(json_file):
            print(f"文件 {json_file} 不存在")
            sys.exit(1)

        with open(json_file, 'r', encoding='utf-8') as f:
            task_data = json.load(f)

        manager.add_task(task_data)

    elif command == "update":
        task_id = sys.argv[2]
        # 这里需要更复杂的逻辑来处理更新
        print("更新功能需要更多参数，请使用代码直接调用")

    elif command == "delete":
        task_id = sys.argv[2]
        manager.delete_task(task_id)

    elif command == "changelog":
        task_id = sys.argv[2]
        version = sys.argv[3]
        changes = input("请输入变更内容（多条用逗号分隔）: ").split(',')
        changes = [c.strip() for c in changes]
        manager.add_changelog(task_id, version, changes)

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
