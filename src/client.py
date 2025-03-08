from typing import Dict, Any, Optional
from telethon import TelegramClient
from loguru import logger
import python_socks

class TelegramClientManager:
    """Telegram客户端管理类，负责客户端的创建和管理"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None

    async def setup_proxy(self) -> Optional[Dict[str, Any]]:
        """设置代理配置"""
        if not self.config['proxy']['enabled']:
            return None

        return {
            'proxy_type': python_socks.ProxyType.SOCKS5 
                         if self.config['proxy']['type'].lower() == 'socks5' 
                         else python_socks.ProxyType.SOCKS4,
            'addr': self.config['proxy']['host'],
            'port': self.config['proxy']['port'],
            'username': self.config['proxy']['username'],
            'password': self.config['proxy']['password']
        }

    async def create_client(self) -> TelegramClient:
        """创建并返回Telegram客户端实例"""
        proxy = await self.setup_proxy()
        self.client = TelegramClient(
            self.config['session_name'],
            self.config['api_id'],
            self.config['api_hash'],
            proxy=proxy
        )
        return self.client

    async def connect_and_authorize(self) -> None:
        """连接并授权客户端"""
        if not self.client:
            await self.create_client()
            
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.info("请使用手机号码登录")
                phone = input("请输入您的手机号码 (格式: +86xxxxxxxxxx): ")
                await self.client.send_code_request(phone=phone)
                code = input("请输入收到的验证码: ")
                await self.client.sign_in(phone=phone, code=code)
                logger.info("登录成功")
            else:
                logger.info("已使用现有会话登录")
        except Exception as e:
            logger.error(f"连接或授权失败: {e}")
            raise

    async def disconnect(self) -> None:
        """断开客户端连接"""
        if self.client:
            await self.client.disconnect()
            logger.info("已断开Telegram客户端连接")