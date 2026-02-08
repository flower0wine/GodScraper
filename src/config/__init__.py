"""
配置和状态管理模块
负责应用程序状态的持久化和配置管理
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class StateManager:
    """
    状态管理器

    负责加载和保存应用程序状态到JSON文件

    Attributes:
        state_file: 状态文件路径
        state: 当前状态字典
    """

    def __init__(self, state_file: str = "state.json"):
        """
        初始化状态管理器

        Args:
            state_file: 状态文件名
        """
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """
        加载状态文件

        Returns:
            状态字典，如果文件不存在或损坏则返回默认状态
        """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # 返回默认状态
        return {
            "api_id": None,
            "api_hash": None,
            "channels": {},
            "channel_names": {},
            "scrape_media": True,
        }

    def load_state(self) -> Dict[str, Any]:
        """
        加载状态（公开接口）

        Returns:
            当前状态字典
        """
        return self._load_state()

    def save_state(self) -> bool:
        """
        保存当前状态到文件

        Returns:
            是否保存成功
        """
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Failed to save state: {e}")
            return False

    def get_api_credentials(self) -> tuple:
        """
        获取API凭证

        Returns:
            (api_id, api_hash) 元组
        """
        return self.state.get("api_id"), self.state.get("api_hash")

    def set_api_credentials(self, api_id: int, api_hash: str) -> None:
        """
        设置API凭证

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
        """
        self.state["api_id"] = api_id
        self.state["api_hash"] = api_hash
        self.save_state()

    def add_channel(self, channel_id: str, username: Optional[str] = None) -> None:
        """
        添加频道到监控列表

        Args:
            channel_id: 频道ID
            username: 频道用户名
        """
        if channel_id not in self.state["channels"]:
            self.state["channels"][channel_id] = 0

        if "channel_names" not in self.state:
            self.state["channel_names"] = {}

        if username:
            self.state["channel_names"][channel_id] = username

        self.save_state()

    def remove_channel(self, channel_id: str) -> bool:
        """
        从监控列表移除频道

        Args:
            channel_id: 频道ID

        Returns:
            是否成功移除
        """
        if channel_id in self.state["channels"]:
            del self.state["channels"][channel_id]
            self.state["channel_names"].pop(channel_id, None)
            self.save_state()
            return True
        return False

    def update_channel_progress(self, channel_id: str, last_message_id: int) -> None:
        """
        更新频道抓取进度

        Args:
            channel_id: 频道ID
            last_message_id: 最后处理的消息ID
        """
        if channel_id in self.state["channels"]:
            self.state["channels"][channel_id] = last_message_id
            self.save_state()

    def get_all_channels(self) -> Dict[str, int]:
        """
        获取所有监控频道

        Returns:
            频道ID到最后消息ID的映射
        """
        return self.state.get("channels", {})

    def get_channel_name(self, channel_id: str) -> str:
        """
        获取频道名称

        Args:
            channel_id: 频道ID

        Returns:
            频道名称或 'Unknown'
        """
        return self.state.get("channel_names", {}).get(channel_id, "Unknown")

    def is_media_scraping_enabled(self) -> bool:
        """
        检查是否启用了媒体抓取

        Returns:
            是否启用媒体抓取
        """
        return self.state.get("scrape_media", True)

    def set_media_scraping(self, enabled: bool) -> None:
        """
        设置媒体抓取开关

        Args:
            enabled: 是否启用
        """
        self.state["scrape_media"] = enabled
        self.save_state()
