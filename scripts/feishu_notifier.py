#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书消息发送工具 - WebSocket 直连版
直接通过 WebSocket 发送消息到飞书，无需 API 认证
"""

import requests
import json
import websocket
import threading
import time
from queue import Queue

# 飞书 WebSocket 配置
FEISHU_WS_URL = "wss://im-api-v2.feishu.cn/ws/"  # 正确的飞书 WebSocket 地址


class FeishuWebSocketNotifier:
    """通过 WebSocket 直连飞书发送消息"""

    def __init__(self):
        self.ws = None
        self.connected = False
        self.message_queue = Queue()
        self.chat_id = "oc_ff08c55a23630937869cd222dad0bf14"  # 从 feishu_receive_ids.json 获取

    def connect(self):
        """建立 WebSocket 连接"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Sec-WebSocket-Protocol": "lark"
            }
            import ssl
            self.ws = websocket.WebSocketApp(
                FEISHU_WS_URL,
                header=headers,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                sslopt={"cert_reqs": ssl.CERT_NONE}
            )
            
            # 在后台线程运行 WebSocket
            threading.Thread(target=self.ws.run_forever, daemon=True).start()
            
            # 等待连接建立
            timeout = 5
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
                
            return self.connected
        except Exception as e:
            print(f"WebSocket 连接失败: {e}")
            return False

    def on_open(self, ws):
        """WebSocket 连接成功"""
        print("✅ WebSocket 连接成功")
        self.connected = True
        
        # 启动消息发送线程
        threading.Thread(target=self._send_queued_messages, daemon=True).start()

    def on_message(self, ws, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            print(f"[飞书] 收到消息: {data}")
            
            # 处理心跳响应
            if data.get('type') == 'pong':
                print("🔄 收到心跳响应")
        except:
            print(f"[飞书] 原始消息: {message}")

    def on_error(self, ws, error):
        """处理错误"""
        print(f"❌ WebSocket 错误: {error}")
        self.connected = False

    def on_close(self, ws, close_status_code, close_msg):
        """处理连接关闭"""
        print(f"🔌 WebSocket 连接关闭: {close_status_code} - {close_msg}")
        self.connected = False

    def _send_queued_messages(self):
        """发送队列中的消息"""
        while self.connected:
            try:
                message = self.message_queue.get(timeout=1)
                self._send_message(message)
                self.message_queue.task_done()
            except:
                continue

    def _send_message(self, content):
        """发送消息到飞书"""
        if not self.connected:
            print("❌ 未连接到 WebSocket")
            return False

        try:
            # 构建飞书消息格式
            message = {
                "id": f"msg_{int(time.time()*1000)}",
                "type": "message",
                "chat_id": self.chat_id,
                "content": {
                    "text": content
                }
            }
            
            # 发送消息
            self.ws.send(json.dumps(message))
            print(f"📤 已发送消息到飞书群")
            return True
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
            return False

    def send(self, message):
        """添加消息到发送队列"""
        self.message_queue.put(message)
        return True


# 全局通知器实例
_notifier = None

def get_notifier():
    """获取或创建通知器实例"""
    global _notifier
    if _notifier is None or not _notifier.connected:
        _notifier = FeishuWebSocketNotifier()
        if not _notifier.connect():
            print("⚠️ 无法连接到飞书 WebSocket")
    return _notifier

def send_feishu_message(message):
    """
    发送消息到飞书群
    
    Args:
        message: 消息内容

    Returns:
        bool: 发送是否成功
    """
    notifier = get_notifier()
    if notifier.connected:
        return notifier.send(message)
    else:
        print("❌ 无法发送消息: 未连接")
        return False


def main():
    """测试飞书消息发送"""
    print("🚀 测试飞书 WebSocket 消息发送...")

    # 测试消息
    test_message = """
📊 T01龙头战法测试消息

✅ WebSocket 直连模式已启用
⏱ 当前时间: """ + time.strftime("%Y-%m-%d %H:%M:%S")

    # 发送测试消息
    if send_feishu_message(test_message):
        print("🎉 测试消息已加入发送队列")
    else:
        print("❌ 测试消息发送失败")

    # 保持连接一段时间
    time.sleep(5)

if __name__ == "__main__":
    main()