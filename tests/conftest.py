import pytest
from unittest.mock import MagicMock, AsyncMock
from telethon import TelegramClient
from src.config import ConfigManager

@pytest.fixture
def mock_config():
    """模拟配置数据"""
    return {
        'api_id': '123456',
        'api_hash': 'test_hash',
        'session_name': 'test_session',
        'source_channel': '@test_source',
        'target_channel': '@test_target',
        'message_range': {'start_id': 1, 'end_id': 10},
        'message_interval': 1,
        'proxy': {
            'enabled': False,
            'type': 'socks5',
            'host': 'localhost',
            'port': 1080,
            'username': '',
            'password': ''
        }
    }

@pytest.fixture
def mock_telegram_client():
    """模拟Telegram客户端"""
    client = MagicMock(spec=TelegramClient)
    # 模拟异步方法
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=True)
    client.get_entity = AsyncMock()
    client.get_messages = AsyncMock()
    client.forward_messages = AsyncMock()
    return client

@pytest.fixture
def mock_config_manager(mock_config):
    """模拟配置管理器"""
    ConfigManager.load_config = AsyncMock(return_value=mock_config)
    return ConfigManager