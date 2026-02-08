"""
数据模型模块
定义应用中使用的核心数据结构
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MessageData:
    """
    消息数据模型

    Attributes:
        message_id: 消息唯一标识
        date: 消息发送时间
        sender_id: 发送者ID
        first_name: 发送者名字
        last_name: 发送者姓氏
        username: 发送者用户名
        message: 消息内容
        media_type: 媒体类型
        media_path: 媒体本地路径
        reply_to: 回复的消息ID
        post_author: 频道帖子作者
        views: 浏览量
        forwards: 转发数
        reactions: 表情反应
    """

    message_id: int
    date: str
    sender_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    message: str
    media_type: Optional[str]
    media_path: Optional[str]
    reply_to: Optional[int]
    post_author: Optional[str]
    views: Optional[int]
    forwards: Optional[int]
    reactions: Optional[str]


@dataclass
class ChannelInfo:
    """
    频道信息模型

    Attributes:
        channel_id: 频道ID
        channel_name: 频道名称
        username: 频道用户名
        channel_type: 频道类型 (Channel/Group)
        last_message_id: 最后抓取的消息ID
    """

    channel_id: str
    channel_name: str
    username: str
    channel_type: str
    last_message_id: int = 0
