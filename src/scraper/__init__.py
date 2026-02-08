"""
消息抓取模块
负责从Telegram频道抓取消息数据
"""

import asyncio
import sys
from typing import AsyncIterator, List, Optional, Tuple

from telethon import TelegramClient
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    User,
)
from telethon.tl.types import PeerChannel

from src.models import MessageData


class MessageParser:
    """
    消息解析器

    负责将Telegram消息对象解析为数据模型
    """

    @staticmethod
    def parse_reactions(message) -> Optional[str]:
        """
        解析消息的表情反应

        Args:
            message: Telegram消息对象

        Returns:
            格式化的反应字符串
        """
        if not message.reactions or not message.reactions.results:
            return None

        reactions_parts = []
        for reaction in message.reactions.results:
            emoji = getattr(reaction.reaction, "emoticon", "")
            count = reaction.count
            if emoji:
                reactions_parts.append(f"{emoji} {count}")

        return " ".join(reactions_parts) if reactions_parts else None

    @staticmethod
    def parse_sender(
        message,
    ) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
        """
        解析消息发送者信息

        Args:
            message: Telegram消息对象

        Returns:
            (sender_id, first_name, last_name, username) 元组
        """
        sender = message.sender

        if isinstance(sender, User):
            return (
                message.sender_id,
                getattr(sender, "first_name", None),
                getattr(sender, "last_name", None),
                getattr(sender, "username", None),
            )

        return message.sender_id, None, None, None

    def parse(self, message) -> MessageData:
        """
        解析单条消息

        Args:
            message: Telegram消息对象

        Returns:
            MessageData对象
        """
        sender_id, first_name, last_name, username = self.parse_sender(message)
        reactions = self.parse_reactions(message)

        return MessageData(
            message_id=message.id,
            date=message.date.strftime("%Y-%m-%d %H:%M:%S"),
            sender_id=sender_id or 0,
            first_name=first_name,
            last_name=last_name,
            username=username,
            message=message.message or "",
            media_type=message.media.__class__.__name__ if message.media else None,
            media_path=None,
            reply_to=message.reply_to_msg_id if message.reply_to else None,
            post_author=message.post_author,
            views=message.views,
            forwards=message.forwards,
            reactions=reactions,
        )


class ProgressBar:
    """
    进度条

    在终端中显示进度信息
    """

    def __init__(self, description: str = "Progress"):
        """
        初始化进度条

        Args:
            description: 进度描述
        """
        self.description = description
        self.bar_length = 30

    def update(self, current: int, total: int) -> None:
        """
        更新进度条

        Args:
            current: 当前完成数量
            total: 总数量
        """
        progress = (current / total) * 100 if total > 0 else 0
        filled_length = int(self.bar_length * current // total)
        bar = "█" * filled_length + "░" * (self.bar_length - filled_length)

        sys.stdout.write(
            f"\r{self.description}: [{bar}] {progress:.1f}% ({current}/{total})"
        )
        sys.stdout.flush()

    def complete(self, message: str = "Done") -> None:
        """
        完成进度条

        Args:
            message: 完成消息
        """
        sys.stdout.write(f"\n{message}\n")
        sys.stdout.flush()


class ChannelScraper:
    """
    频道抓取器

    负责从Telegram频道抓取消息
    """

    def __init__(
        self,
        client: TelegramClient,
        db_manager,
        media_manager,
        state_manager,
        batch_size: int = 100,
        max_concurrent_downloads: int = 5,
    ):
        """
        初始化频道抓取器

        Args:
            client: Telegram客户端
            db_manager: 数据库管理器
            media_manager: 媒体管理器
            state_manager: 状态管理器
            batch_size: 批量处理大小
            max_concurrent_downloads: 最大并发下载数
        """
        self.client = client
        self.db_manager = db_manager
        self.media_manager = media_manager
        self.state_manager = state_manager
        self.batch_size = batch_size
        self.max_concurrent_downloads = max_concurrent_downloads
        self.parser = MessageParser()

    async def get_entity(self, channel: str):
        """
        获取频道实体

        Args:
            channel: 频道标识符

        Returns:
            Telegram实体
        """
        if channel.startswith("-"):
            return await self.client.get_entity(PeerChannel(int(channel)))
        return await self.client.get_entity(channel)

    async def count_messages(self, entity) -> int:
        """
        统计消息总数

        Args:
            entity: Telegram实体

        Returns:
            消息总数
        """
        result = await self.client.get_messages(entity, limit=1)
        return result.total or 0

    async def iterate_messages(
        self, entity, offset_id: int = 0, reverse: bool = True
    ) -> AsyncIterator:
        """
        异步迭代消息

        Args:
            entity: Telegram实体
            offset_id: 起始消息ID
            reverse: 是否反向迭代

        Yields:
            Telegram消息对象
        """
        async for message in self.client.iter_messages(
            entity, offset_id=offset_id, reverse=reverse
        ):
            yield message

    async def scrape(
        self, channel: str, offset_id: int = 0, state_save_interval: int = 50
    ) -> int:
        """
        抓取频道消息

        Args:
            channel: 频道标识符
            offset_id: 起始消息ID（用于增量抓取）
            state_save_interval: 状态保存间隔

        Returns:
            抓取的消息总数
        """
        entity = await self.get_entity(channel)
        total_messages = await self.count_messages(entity)

        if total_messages == 0:
            print(f"频道 {channel} 中未找到消息")
            return 0

        print(f"找到 {total_messages} 条消息")

        message_batch: List[MessageData] = []
        media_messages = []
        processed_count = 0
        last_message_id = offset_id

        progress_bar = ProgressBar("📄 Messages")

        async for message in self.iterate_messages(entity, offset_id):
            try:
                # 解析消息
                msg_data = self.parser.parse(message)
                message_batch.append(msg_data)

                # 收集需要下载媒体的消息
                if self.state_manager.is_media_scraping_enabled():
                    if message.media and not isinstance(
                        message.media, MessageMediaWebPage
                    ):
                        media_messages.append(message)

                last_message_id = message.id
                processed_count += 1

                # 批量保存消息
                if len(message_batch) >= self.batch_size:
                    self.db_manager.batch_insert_messages(channel, message_batch)
                    message_batch.clear()

                # 定期保存状态
                if processed_count % state_save_interval == 0:
                    self.state_manager.update_channel_progress(channel, last_message_id)

                # 更新进度条
                progress_bar.update(processed_count, total_messages)

            except Exception as e:
                print(f"\n处理消息 {message.id} 时出错: {e}")

        # 保存剩余消息
        if message_batch:
            self.db_manager.batch_insert_messages(channel, message_batch)

        # 下载媒体
        if media_messages:
            successful = await self.media_manager.download_channel_media(
                channel,
                media_messages,
                lambda c, t, s: ProgressBar("📥 Media").update(c, t),
            )
            print(f"\n✅ 媒体下载完成! ({successful}/{len(media_messages)} 成功)")

        # 更新最终状态
        self.state_manager.update_channel_progress(channel, last_message_id)
        progress_bar.complete(f"\n完成频道 {channel} 的抓取")

        return processed_count


class ContinuousScraper:
    """
    连续抓取器

    负责定时增量抓取新消息
    """

    def __init__(self, scraper: ChannelScraper, interval: int = 60):
        """
        初始化连续抓取器

        Args:
            scraper: 频道抓取器
            interval: 检查间隔（秒）
        """
        self.scraper = scraper
        self.interval = interval
        self.active = False

    async def start(self) -> None:
        """
        开始连续抓取
        """
        self.active = True

        try:
            while self.active:
                start_time = asyncio.get_event_loop().time()

                channels = self.scraper.state_manager.get_all_channels()
                for channel in channels:
                    if not self.active:
                        break

                    last_id = channels[channel]
                    print(f"\n检查频道 {channel} 的新消息...")
                    await self.scraper.scrape(channel, last_id)

                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.interval - elapsed)

                if sleep_time > 0 and self.active:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            print("连续抓取已停止")
        finally:
            self.active = False

    def stop(self) -> None:
        """
        停止连续抓取
        """
        self.active = False
