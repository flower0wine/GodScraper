"""
媒体下载模块
负责图片和文档的异步下载管理
"""

import asyncio
from pathlib import Path
from typing import Optional

from telethon.errors import FloodWaitError
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
)


class MediaDownloader:
    """
    媒体下载器

    负责从Telegram频道下载媒体文件

    Attributes:
        max_concurrent_downloads: 最大并发下载数
        scrape_media: 是否启用媒体抓取
    """

    def __init__(self, max_concurrent_downloads: int = 5, scrape_media: bool = True):
        """
        初始化媒体下载器

        Args:
            max_concurrent_downloads: 最大并发下载数
            scrape_media: 是否启用媒体抓取
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        self.scrape_media = scrape_media

    async def download(
        self, channel: str, message, media_path_callback=None
    ) -> Optional[str]:
        """
        下载单条消息的媒体

        Args:
            channel: 频道标识符
            message: Telegram消息对象
            media_path_callback: 可选的媒体路径回调函数

        Returns:
            下载后的媒体路径，失败返回None
        """
        if not self.scrape_media or not message.media:
            return None

        # 跳过网页媒体
        if isinstance(message.media, MessageMediaWebPage):
            return None

        try:
            channel_dir = Path(channel)
            media_folder = channel_dir / "media"
            media_folder.mkdir(exist_ok=True)

            # 确定文件名
            if isinstance(message.media, MessageMediaPhoto):
                original_name = getattr(message.file, "name", None) or "photo.jpg"
                ext = "jpg"
            elif isinstance(message.media, MessageMediaDocument):
                ext = getattr(message.file, "ext", "bin") if message.file else "bin"
                original_name = getattr(message.file, "name", None) or f"document.{ext}"
            else:
                return None

            # 生成唯一文件名
            base_name = Path(original_name).stem
            extension = Path(original_name).suffix or f".{ext}"
            unique_filename = f"{message.id}-{base_name}{extension}"
            download_path = media_folder / unique_filename

            # 检查是否已下载
            existing_files = list(media_folder.glob(f"{message.id}-*"))
            if existing_files:
                return str(existing_files[0])

            # 下载媒体（带重试）
            for attempt in range(3):
                try:
                    downloaded_path = await message.download_media(
                        file=str(download_path)
                    )
                    if downloaded_path and Path(downloaded_path).exists():
                        return downloaded_path
                    return None

                except FloodWaitError as e:
                    if attempt < 2:
                        await asyncio.sleep(e.seconds)
                    else:
                        return None

                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                    else:
                        return None

            return None

        except Exception:
            return None

    def create_download_task(self, channel: str, message, semaphore: asyncio.Semaphore):
        """
        创建带并发控制的下载任务

        Args:
            channel: 频道标识符
            message: Telegram消息对象
            semaphore: 并发控制信号量

        Returns:
            异步下载任务
        """

        async def _download():
            async with semaphore:
                return await self.download(channel, message)

        return asyncio.create_task(_download())


class MediaManager:
    """
    媒体管理器

    协调媒体下载和状态更新
    """

    def __init__(self, downloader: MediaDownloader, db_manager, state_manager):
        """
        初始化媒体管理器

        Args:
            downloader: 媒体下载器
            db_manager: 数据库管理器
            state_manager: 状态管理器
        """
        self.downloader = downloader
        self.db_manager = db_manager
        self.state_manager = state_manager

    async def download_channel_media(
        self, channel: str, messages, progress_callback=None
    ) -> int:
        """
        下载频道中所有消息的媒体

        Args:
            channel: 频道标识符
            messages: 消息列表
            progress_callback: 进度回调函数

        Returns:
            成功下载的媒体数量
        """
        if not self.state_manager.is_media_scraping_enabled():
            return 0

        media_messages = [
            msg
            for msg in messages
            if msg.media and not isinstance(msg.media, MessageMediaWebPage)
        ]

        if not media_messages:
            return 0

        total_media = len(media_messages)
        completed = 0
        successful = 0

        semaphore = asyncio.Semaphore(self.downloader.max_concurrent_downloads)
        batch_size = 10

        for i in range(0, len(media_messages), batch_size):
            batch = media_messages[i : i + batch_size]
            tasks = [
                self.downloader.create_download_task(channel, msg, semaphore)
                for msg in batch
            ]

            for j, task in enumerate(tasks):
                try:
                    media_path = await task
                    if media_path:
                        self.db_manager.update_media_path(
                            channel, batch[j].id, media_path
                        )
                        successful += 1
                except Exception:
                    pass

                completed += 1
                if progress_callback:
                    progress_callback(completed, total_media, successful)

        return successful

    async def fix_missing_media(self, channel: str, entity) -> int:
        """
        修复缺失的媒体文件

        Args:
            channel: 频道标识符
            entity: Telegram实体

        Returns:
            成功修复的媒体数量
        """
        missing = self.db_manager.get_missing_media_messages(channel)

        if not missing:
            return 0

        semaphore = asyncio.Semaphore(self.downloader.max_concurrent_downloads)
        completed = 0
        successful = 0

        for i in range(0, len(missing), 10):
            batch_ids = [msg[0] for msg in missing[i : i + 10]]
            messages = await self.state_manager.client.get_messages(
                entity, ids=batch_ids
            )

            valid_messages = [
                msg
                for msg in messages
                if msg and msg.media and not isinstance(msg.media, MessageMediaWebPage)
            ]

            tasks = [
                self.downloader.create_download_task(channel, msg, semaphore)
                for msg in valid_messages
            ]

            for j, task in enumerate(tasks):
                try:
                    media_path = await task
                    if media_path:
                        self.db_manager.update_media_path(
                            channel, valid_messages[j].id, media_path
                        )
                        successful += 1
                except Exception:
                    pass

                completed += 1

        return successful
