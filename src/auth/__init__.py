"""
认证模块
负责Telegram客户端的认证和授权
"""

import asyncio
from typing import Optional

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

import qrcode
from io import StringIO


class AuthManager:
    """
    认证管理器

    处理Telegram账户的认证流程

    Attributes:
        client: Telegram客户端实例
        api_id: API ID
        api_hash: API Hash
    """

    def __init__(self, api_id: int, api_hash: str):
        """
        初始化认证管理器

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.client: Optional[TelegramClient] = None

    async def connect(self) -> bool:
        """
        连接到Telegram服务器

        Returns:
            是否连接成功
        """
        self.client = TelegramClient("session", self.api_id, self.api_hash)

        try:
            await self.client.connect()
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    async def is_authorized(self) -> bool:
        """
        检查是否已授权

        Returns:
            是否已授权
        """
        if not self.client:
            return False
        return await self.client.is_user_authorized()

    async def disconnect(self) -> None:
        """
        断开与Telegram服务器的连接
        """
        if self.client:
            await self.client.disconnect()

    def _display_qr_code_ascii(self, qr_login) -> None:
        """
        在终端中显示QR码

        Args:
            qr_login: QR登录对象
        """
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(qr_login.url)
        qr.make()

        f = StringIO()
        qr.print_ascii(out=f)
        f.seek(0)
        print(f.read())

    async def authenticate_with_qr(self) -> bool:
        """
        使用QR码进行认证

        Returns:
            是否认证成功
        """
        print("\n选择QR码认证...")
        print("请使用Telegram扫描以下QR码:")
        print("1. 在手机上打开Telegram")
        print("2. 进入设置 > 设备 > 扫描QR码")
        print("3. 扫描下方二维码\n")

        try:
            qr_login = await self.client.qr_login()
            self._display_qr_code_ascii(qr_login)

            await qr_login.wait()
            print("\n✅ QR码认证成功!")
            return True

        except SessionPasswordNeededError:
            password = input("已启用两步验证。请输入密码: ")
            await self.client.sign_in(password=password)
            print("✅ 两步验证登录成功!")
            return True

        except Exception as e:
            print(f"\n❌ QR码认证失败: {e}")
            return False

    async def authenticate_with_phone(self) -> bool:
        """
        使用手机号进行认证

        Returns:
            是否认证成功
        """
        phone = input("请输入手机号: ")
        await self.client.send_code_request(phone)
        code = input("请输入收到的验证码: ")

        try:
            await self.client.sign_in(phone, code)
            print("\n✅ 手机号认证成功!")
            return True

        except SessionPasswordNeededError:
            password = input("已启用两步验证。请输入密码: ")
            await self.client.sign_in(password=password)
            print("✅ 两步验证登录成功!")
            return True

        except Exception as e:
            print(f"\n❌ 手机号认证失败: {e}")
            return False

    async def authenticate(self) -> bool:
        """
        执行认证流程

        Returns:
            是否认证成功
        """
        if not await self.connect():
            return False

        if await self.is_authorized():
            print("✅ 已授权!")
            return True

        print("\n=== 选择认证方式 ===")
        print("[1] QR码认证 (推荐 - 无需手机号)")
        print("[2] 手机号认证 (传统方式)")

        while True:
            choice = input("请选择 (1 或 2): ").strip()
            if choice in ["1", "2"]:
                break
            print("请输入 1 或 2")

        success = (
            await self.authenticate_with_qr()
            if choice == "1"
            else await self.authenticate_with_phone()
        )

        if not success:
            print("认证失败，请重试。")
            await self.disconnect()
            return False

        return True


class APICredentialsManager:
    """
    API凭证管理器

    负责获取和验证Telegram API凭证
    """

    @staticmethod
    async def get_credentials_from_user() -> tuple:
        """
        从用户获取API凭证

        Returns:
            (api_id, api_hash) 元组，失败时返回 (None, None)
        """
        print("\n=== 需要配置API凭证 ===")
        print("请从 https://my.telegram.org 获取API凭证")

        try:
            api_id = int(input("请输入API ID: "))
            api_hash = input("请输入API Hash: ")
            return api_id, api_hash

        except ValueError:
            print("无效的API ID，必须是数字。")
            return None, None

    @staticmethod
    def validate_credentials(api_id: int, api_hash: str) -> bool:
        """
        验证API凭证格式

        Args:
            api_id: API ID
            api_hash: API Hash

        Returns:
            格式是否有效
        """
        if not api_id or api_id <= 0:
            return False
        if not api_hash or len(api_hash) < 10:
            return False
        return True
