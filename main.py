#!/usr/bin/env python3
"""
Telegram Scraper - 主入口

从Telegram频道抓取消息和媒体文件的工具

功能:
- 消息抓取和存储
- 媒体文件下载
- 数据导出(CVS/JSON)
- 连续抓取模式
- 多频道管理

使用方法:
    python main.py

作者: Telegram Scraper
版本: 1.0.0
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

# 导入各模块
from src.config import StateManager
from src.database import DatabaseManager
from src.auth import AuthManager, APICredentialsManager
from src.media import MediaDownloader, MediaManager
from src.scraper import ChannelScraper, ContinuousScraper
from src.export import DataExporter, ChannelListExporter
from src.ui import AsciiArt, ChannelSelector, ChannelManager, InteractiveMenu


class TelegramScraperApp:
    """
    Telegram抓取器应用程序

    协调各模块，提供完整的抓取功能
    """

    def __init__(self):
        """
        初始化应用程序
        """
        # 初始化核心组件
        self.state_manager = StateManager()
        self.db_manager = DatabaseManager()
        self.media_downloader = MediaDownloader(
            max_concurrent_downloads=5,
            scrape_media=self.state_manager.is_media_scraping_enabled(),
        )
        self.media_manager = MediaManager(
            self.media_downloader, self.db_manager, self.state_manager
        )
        self.scraper: Optional[ChannelScraper] = None
        self.continuous_scraper: Optional[ContinuousScraper] = None
        self.client: Optional[TelegramClient] = None

        # 初始化UI组件
        self.channel_selector = ChannelSelector(self.state_manager)
        self.channel_manager = ChannelManager(self.state_manager)
        self.data_exporter = DataExporter(self.db_manager)
        self.channel_list_exporter = ChannelListExporter()

        # 状态标志
        self.continuous_scraping_active = False

    async def initialize_client(self) -> bool:
        """
        初始化Telegram客户端

        Returns:
            是否初始化成功
        """
        # 检查API凭证
        api_id, api_hash = self.state_manager.get_api_credentials()

        if not api_id or not api_hash:
            api_id, api_hash = await APICredentialsManager.get_credentials_from_user()
            if not api_id or not api_hash:
                print("无法获取API凭证，退出。")
                return False

            self.state_manager.set_api_credentials(api_id, api_id)

        # 创建认证管理器
        auth_manager = AuthManager(api_id, api_hash)

        # 执行认证
        if not await auth_manager.authenticate():
            print("认证失败，退出。")
            return False

        # 保存客户端引用
        self.client = auth_manager.client

        # 初始化抓取器
        self.scraper = ChannelScraper(
            client=self.client,
            db_manager=self.db_manager,
            media_manager=self.media_manager,
            state_manager=self.state_manager,
        )

        return True

    async def list_and_add_channels(self) -> None:
        """
        列出并添加频道
        """
        if not self.client:
            print("客户端未初始化")
            return

        print("\n列出账户加入的频道和群组:")
        count = 1
        channels_data = []

        try:
            async for dialog in self.client.iter_dialogs():
                entity = dialog.entity

                # 过滤掉系统账户
                if dialog.id == 777000:
                    continue

                if isinstance(entity, Channel) or isinstance(entity, Chat):
                    channel_type = (
                        "频道"
                        if isinstance(entity, Channel) and entity.broadcast
                        else "群组"
                    )
                    username = getattr(entity, "username", None) or "no_username"

                    print(
                        f"[{count}] {dialog.title} (ID: {dialog.id}, 类型: {channel_type}, 用户名: @{username})"
                    )

                    channels_data.append(
                        {
                            "number": count,
                            "channel_name": dialog.title,
                            "channel_id": str(dialog.id),
                            "username": username,
                            "type": channel_type,
                        }
                    )
                    count += 1

            if channels_data:
                self.channel_list_exporter.export(channels_data)

                print("\n从上述列表中添加频道:")
                print("• 单个: 1 或 -1001234567890")
                print("• 多个: 1,3,5 或混合格式")
                print("• 全部: all")
                print("• 直接回车跳过")
                selection = input("\n请选择 (或回车跳过): ").strip()

                if selection:
                    added = self.channel_manager.add_channels(channels_data, selection)
                    if added > 0:
                        await self._view_channels()

        except Exception as e:
            print(f"列出频道时出错: {e}")

    async def _view_channels(self) -> None:
        """
        显示当前频道列表
        """
        channels = self.state_manager.get_all_channels()
        if not channels:
            print("没有保存的频道")
            return

        print("\n当前频道:")
        for i, (channel, last_id) in enumerate(channels.items(), 1):
            try:
                count = self.db_manager.get_message_count(channel)
                name = self.state_manager.get_channel_name(channel)
                print(
                    f"[{i}] {name} (ID: {channel}), 最后消息ID: {last_id}, 消息数: {count}"
                )
            except Exception:
                name = self.state_manager.get_channel_name(channel)
                print(f"[{i}] {name} (ID: {channel}), 最后消息ID: {last_id}")

    async def scrape_channels(self) -> None:
        """
        抓取用户选择的频道
        """
        if not self.scraper:
            print("抓取器未初始化")
            return

        channels = self.state_manager.get_all_channels()
        if not channels:
            print("没有可用的频道，请先使用 [L] 添加频道")
            return

        await self._view_channels()

        print("\n📥 抓取选项:")
        print("• 单个: 1 或 -1001234567890")
        print("• 多个: 1,3,5 或混合格式")
        print("• 全部: all")

        choice = input("\n请选择: ").strip()
        selected_channels = self.channel_selector.parse(choice)

        if selected_channels:
            print(f"\n🚀 开始抓取 {len(selected_channels)} 个频道...")
            for i, channel in enumerate(selected_channels, 1):
                print(f"\n[{i}/{len(selected_channels)}] 正在抓取: {channel}")
                last_id = self.state_manager.get_all_channels().get(channel, 0)
                await self.scraper.scrape(channel, last_id)
            print(f"\n✅ 完成 {len(selected_channels)} 个频道的抓取!")
        else:
            print("❌ 未选择有效的频道")

    async def start_continuous_scraping(self) -> None:
        """
        开始连续抓取
        """
        if not self.scraper:
            print("抓取器未初始化")
            return

        if not self.state_manager.get_all_channels():
            print("没有要监控的频道")
            return

        print("连续抓取已启动，按 Ctrl+C 停止。")

        self.continuous_scraper = ContinuousScraper(self.scraper, interval=60)

        try:
            await self.continuous_scraper.start()
        except asyncio.CancelledError:
            print("\n正在停止连续抓取...")
            self.continuous_scraper.stop()

    async def export_data(self) -> None:
        """
        导出所有频道数据
        """
        channels = self.state_manager.get_all_channels()
        channel_names = {c: self.state_manager.get_channel_name(c) for c in channels}

        self.data_exporter.export_all_channels(channels, channel_names)

    async def rescrape_media(self, channel: str) -> None:
        """
        重新抓取指定频道的媒体

        Args:
            channel: 频道ID
        """
        print(f"正在重新抓取频道 {channel} 的媒体...")
        # 这里可以添加媒体重新抓取逻辑
        print("媒体重新抓取功能待实现")

    async def fix_missing_media(self, channel: str) -> None:
        """
        修复指定频道缺失的媒体

        Args:
            channel: 频道ID
        """
        print(f"正在修复频道 {channel} 缺失的媒体...")
        # 这里可以添加媒体修复逻辑
        print("媒体修复功能待实现")

    async def cleanup(self) -> None:
        """
        清理资源
        """
        print("\n正在清理资源...")
        self.db_manager.close_all_connections()

        if self.client:
            await self.client.disconnect()

    async def run(self) -> None:
        """
        运行应用程序
        """
        # 显示ASCII艺术
        AsciiArt.display_scraper_header()

        # 初始化客户端
        if not await self.initialize_client():
            print("客户端初始化失败，退出。")
            return

        # 创建交互菜单
        menu = InteractiveMenu(
            state_manager=self.state_manager,
            db_manager=self.db_manager,
            channel_selector=self.channel_selector,
            channel_manager=self.channel_manager,
            on_scrape=self.scrape_channels,
            on_continuous=self.start_continuous_scraping,
            on_export=self.export_data,
            on_list_channels=self.list_and_add_channels,
            on_rescrape=self.rescrape_media,
            on_fix_media=self.fix_missing_media,
            on_quit=self.cleanup,
        )

        # 运行菜单
        try:
            await menu.run()
        finally:
            await self.cleanup()


async def main():
    """
    主函数
    """
    app = TelegramScraperApp()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被中断，正在退出...")
        sys.exit(0)
