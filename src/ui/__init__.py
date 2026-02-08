"""
用户界面模块
负责命令行交互界面和菜单系统
"""

import asyncio
from typing import Callable, Dict, List, Optional

from src.config import StateManager
from src.database import DatabaseManager
from src.export import ChannelListExporter


class AsciiArt:
    """
    ASCII艺术展示
    """

    @staticmethod
    def display_scraper_header():
        """
        显示抓取器ASCII艺术
        """
        WHITE = "\033[97m"
        RESET = "\033[0m"
        art = r"""
 ___________________  _________
 \__    ___/  _____/ /   _____/
   |    | /   \  ___ \_____  \
   |    | \    \_\  \/        \
   |____|  \______  /_______  /
                  \/        \/
        """
        print(WHITE + art + RESET)


class ChannelSelector:
    """
    频道选择器

    负责解析用户的频道选择输入
    """

    def __init__(self, state_manager: StateManager):
        """
        初始化频道选择器

        Args:
            state_manager: 状态管理器
        """
        self.state_manager = state_manager

    def parse(self, choice: str) -> List[str]:
        """
        解析选择输入

        Args:
            choice: 用户输入的选择字符串

        Returns:
            选中的频道ID列表
        """
        channels_list = list(self.state_manager.get_all_channels().keys())
        selected_channels = []

        if choice.lower() == "all":
            return channels_list

        for selection in [x.strip() for x in choice.split(",")]:
            try:
                if selection.startswith("-"):
                    if selection in self.state_manager.get_all_channels():
                        selected_channels.append(selection)
                    else:
                        print(f"未找到频道ID {selection}")
                else:
                    num = int(selection)
                    if 1 <= num <= len(channels_list):
                        selected_channels.append(channels_list[num - 1])
                    else:
                        print(
                            f"无效的频道编号: {num}，有效范围: 1-{len(channels_list)}"
                        )
            except ValueError:
                print(f"无效的输入: {selection}，请使用数字(1,2,3)或完整ID(-100123...)")

        return selected_channels


class ChannelManager:
    """
    频道管理器

    负责添加和移除频道
    """

    def __init__(self, state_manager: StateManager):
        """
        初始化频道管理器

        Args:
            state_manager: 状态管理器
        """
        self.state_manager = state_manager

    def add_channels(self, channels_data: List[Dict], selection: str) -> int:
        """
        添加选中的频道

        Args:
            channels_data: 可用频道列表
            selection: 用户选择

        Returns:
            添加的频道数量
        """
        if not selection:
            return 0

        added_count = 0

        if selection.lower() == "all":
            for channel_info in channels_data:
                channel_id = channel_info["channel_id"]
                if channel_id not in self.state_manager.get_all_channels():
                    self.state_manager.add_channel(channel_id, channel_info["username"])
                    print(
                        f"✅ 已添加频道 {channel_info['channel_name']} (ID: {channel_id})"
                    )
                    added_count += 1
                else:
                    print(f"频道 {channel_info['channel_name']} 已添加")
        else:
            for sel in [x.strip() for x in selection.split(",")]:
                try:
                    if sel.startswith("-"):
                        channel_id = sel
                        channel_info = next(
                            (c for c in channels_data if c["channel_id"] == channel_id),
                            None,
                        )
                        if not channel_info:
                            print(f"未找到频道ID {channel_id}")
                            continue
                    else:
                        num = int(sel)
                        if 1 <= num <= len(channels_data):
                            channel_info = channels_data[num - 1]
                            channel_id = channel_info["channel_id"]
                        else:
                            print(f"无效的编号: {num}，请选择 1-{len(channels_data)}")
                            continue

                    if channel_id in self.state_manager.get_all_channels():
                        print(f"频道 {channel_info['channel_name']} 已添加")
                    else:
                        self.state_manager.add_channel(
                            channel_id, channel_info["username"]
                        )
                        print(
                            f"✅ 已添加频道 {channel_info['channel_name']} (ID: {channel_id})"
                        )
                        added_count += 1

                except ValueError:
                    print(f"无效的输入: {sel}")

        if added_count > 0:
            self.state_manager.save_state()
            print(f"\n🎉 已添加 {added_count} 个新频道!")

        return added_count

    def remove_channels(self, selected_channels: List[str]) -> int:
        """
        移除选中的频道

        Args:
            selected_channels: 要移除的频道ID列表

        Returns:
            移除的频道数量
        """
        removed_count = 0

        for channel in selected_channels:
            if self.state_manager.remove_channel(channel):
                print(f"✅ 已移除频道 {channel}")
                removed_count += 1
            else:
                print(f"❌ 未找到频道 {channel}")

        if removed_count > 0:
            self.state_manager.save_state()
            print(f"\n🎉 已移除 {removed_count} 个频道!")

        return removed_count


class InteractiveMenu:
    """
    交互式菜单

    提供命令行菜单界面
    """

    def __init__(
        self,
        state_manager: StateManager,
        db_manager: DatabaseManager,
        channel_selector: ChannelSelector,
        channel_manager: ChannelManager,
        on_scrape: Callable,
        on_continuous: Callable,
        on_export: Callable,
        on_list_channels: Callable,
        on_rescrape: Callable,
        on_fix_media: Callable,
        on_quit: Callable,
    ):
        """
        初始化交互式菜单

        Args:
            state_manager: 状态管理器
            db_manager: 数据库管理器
            channel_selector: 频道选择器
            channel_manager: 频道管理器
            各回调函数...
        """
        self.state_manager = state_manager
        self.db_manager = db_manager
        self.channel_selector = channel_selector
        self.channel_manager = channel_manager
        self.on_scrape = on_scrape
        self.on_continuous = on_continuous
        self.on_export = on_export
        self.on_list_channels = on_list_channels
        self.on_rescrape = on_rescrape
        self.on_fix_media = on_fix_media
        self.on_quit = on_quit

    def display(self) -> None:
        """
        显示主菜单
        """
        media_status = "ON" if self.state_manager.is_media_scraping_enabled() else "OFF"

        print("\n" + "=" * 40)
        print("           TELEGRAM SCRAPER")
        print("=" * 40)
        print("[S] 抓取频道")
        print("[C] 连续抓取")
        print(f"[M] 媒体抓取: {media_status}")
        print("[L] 列出和添加频道")
        print("[R] 移除频道")
        print("[E] 导出数据")
        print("[T] 重新抓取媒体")
        print("[F] 修复缺失的媒体")
        print("[Q] 退出")
        print("=" * 40)

    async def run(self) -> None:
        """
        运行菜单主循环
        """
        try:
            while True:
                self.display()

                choice = input("请选择: ").lower().strip()

                try:
                    if choice == "s":
                        await self.on_scrape()

                    elif choice == "c":
                        await self.on_continuous()

                    elif choice == "m":
                        current = self.state_manager.is_media_scraping_enabled()
                        self.state_manager.set_media_scraping(not current)
                        status = "启用" if not current else "禁用"
                        print(f"\n✅ 媒体抓取已{status}")

                    elif choice == "e":
                        await self.on_export()

                    elif choice == "l":
                        await self.on_list_channels()

                    elif choice == "r":
                        await self._handle_remove_channel()

                    elif choice == "t":
                        await self._handle_rescrape_media()

                    elif choice == "f":
                        await self._handle_fix_media()

                    elif choice == "q":
                        print("\n👋 再见!")
                        await self.on_quit()
                        break

                    else:
                        print("无效选项")

                except Exception as e:
                    print(f"错误: {e}")

        except KeyboardInterrupt:
            print("\n程序被中断，正在退出...")
            await self.on_quit()

    async def _handle_remove_channel(self) -> None:
        """
        处理移除频道
        """
        channels = self.state_manager.get_all_channels()
        if not channels:
            print("没有要移除的频道")
            return

        await self._view_channels()
        print("\n要移除的频道:")
        print("• 单个: 1 或 -1001234567890")
        print("• 多个: 1,2,3 或混合格式")
        selection = input("请选择: ").strip()
        selected = self.channel_selector.parse(selection)

        if selected:
            self.channel_manager.remove_channels(selected)
            await self._view_channels()
        else:
            print("未选择有效的频道")

    async def _handle_rescrape_media(self) -> None:
        """
        处理重新抓取媒体
        """
        channels = self.state_manager.get_all_channels()
        if not channels:
            print("没有可用的频道，请先添加频道")
            return

        await self._view_channels()
        print("\n请输入频道编号(1,2,3...)或完整频道ID(-100123...)")
        selection = input("请选择: ").strip()
        selected = self.channel_selector.parse(selection)

        if len(selected) == 1:
            await self.on_rescrape(selected[0])
        elif len(selected) > 1:
            print("请只选择一个频道进行媒体重新抓取")
        else:
            print("未选择有效的频道")

    async def _handle_fix_media(self) -> None:
        """
        处理修复缺失媒体
        """
        channels = self.state_manager.get_all_channels()
        if not channels:
            print("没有可用的频道，请先添加频道")
            return

        await self._view_channels()
        print("\n请输入频道编号(1,2,3...)或完整频道ID(-100123...)")
        selection = input("请选择: ").strip()
        selected = self.channel_selector.parse(selection)

        if len(selected) == 1:
            await self.on_fix_media(selected[0])
        elif len(selected) > 1:
            print("请只选择一个频道进行媒体修复")
        else:
            print("未选择有效的频道")

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
            except:
                name = self.state_manager.get_channel_name(channel)
                print(f"[{i}] {name} (ID: {channel}), 最后消息ID: {last_id}")
