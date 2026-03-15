#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书消息发送工具
用于发送消息到飞书
"""

import requests
import json

# 飞书配置（从config.json中获取）
FEISHU_APP_ID = "cli_a91352631238dbd7"
FEISHU_APP_SECRET = "mqcyDuIhHnf8DuvKsnG5eb01dUgSj1MF"

# API基础URL
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


class FeishuNotifier:
    """飞书消息发送器"""

    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self.access_token = None
        self.tenant_access_token = None

    def get_tenant_access_token(self):
        """
        获取 tenant_access_token
        """
        try:
            url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
            headers = {"Content-Type": "application/json"}
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()

            result = response.json()

            if result.get('code') == 0:
                self.tenant_access_token = result.get('tenant_access_token')
                return self.tenant_access_token
            else:
                print(f"获取 tenant_access_token 失败: {result.get('msg', '未知错误')}")
                return None

        except Exception as e:
            print(f"获取 tenant_access_token 时发生错误: {e}")
            return None

    def send_message(self, chat_id, message):
        """
        发送消息到飞书群

        Args:
            chat_id: 群聊ID
            message: 消息内容

        Returns:
            bool: 发送是否成功
        """
        # 获取 tenant_access_token
        if not self.get_tenant_access_token():
            print("获取 tenant_access_token 失败")
            return False

        try:
            # 发送消息到指定群聊
            url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type=chat_id"
            headers = {
                "Authorization": f"Bearer {self.tenant_access_token}",
                "Content-Type": "application/json"
            }

            # 构建消息体 - 使用正确的飞书API格式
            data = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": message})
            }

            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()

            result = response.json()

            if result.get('code') == 0:
                print(f"消息发送成功: {result.get('data', {}).get('message_id')}")
                return True
            else:
                print(f"发送消息失败: {result.get('msg', '未知错误')}")
                print(f"错误详情: {result}")
                return False

        except Exception as e:
            print(f"发送消息时发生错误: {e}")
            return False

    def send_card_message(self, chat_id, title, content):
        """
        发送卡片消息到飞书群（更美观的格式）

        Args:
            chat_id: 群聊ID
            title: 卡片标题
            content: 卡片内容

        Returns:
            bool: 发送是否成功
        """
        # 获取 tenant_access_token
        if not self.get_tenant_access_token():
            print("获取 tenant_access_token 失败")
            return False

        try:
            url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type=chat_id"
            headers = {
                "Authorization": f"Bearer {self.tenant_access_token}",
                "Content-Type": "application/json"
            }

            # 构建卡片消息
            card_content = {
                "config": {
                    "wide_screen_mode": True
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{title}**\n\n{content}"
                        }
                    }
                ]
            }

            data = {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card_content)
            }

            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()

            result = response.json()

            if result.get('code') == 0:
                print(f"卡片消息发送成功")
                return True
            else:
                print(f"发送卡片消息失败: {result.get('msg', '未知错误')}")
                return False

        except Exception as e:
            print(f"发送卡片消息时发生错误: {e}")
            return False


# 简化的发送函数
def send_feishu_message(chat_id, message, use_card=False, title=""):
    """
    发送消息到飞书群的简化函数

    Args:
        chat_id: 群聊ID
        message: 消息内容
        use_card: 是否使用卡片格式（默认False）
        title: 卡片标题（use_card=True时使用）

    Returns:
        bool: 发送是否成功
    """
    try:
        notifier = FeishuNotifier()

        if use_card and title:
            return notifier.send_card_message(chat_id, title, message)
        else:
            return notifier.send_message(chat_id, message)

    except Exception as e:
        print(f"发送飞书消息时发生错误: {e}")
        return False


# 测试函数
def main():
    """测试飞书消息发送"""
    print("测试飞书消息发送...")

    # 测试发送文本消息
    chat_id = "oc_ff08c55a23630937869cd222dad0bf14"
    message = "📊 T01龙头战法测试消息\n\n这是一条测试消息，用于验证飞书消息推送功能是否正常。"

    result = send_feishu_message(chat_id, message)
    print(f"发送文本消息: {'成功' if result else '失败'}")


if __name__ == "__main__":
    main()
