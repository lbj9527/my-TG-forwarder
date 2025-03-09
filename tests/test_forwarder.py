import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.app import ForwarderApp
from src.config import ConfigManager, ConfigValidator
from src.client import TelegramClientManager
from src.message import MessageCollector, MessageHandler
from src.utils import parse_channel_link
from telethon import TelegramClient
from telethon.tl.types import Message

@pytest.fixture
def config():
    return {
        'api_id': '12345',
        'api_hash': 'test_hash',
        'proxy': {
            'enabled': True,
            'type': 'socks5',
            'host': '127.0.0.1',
            'port': 7890,
            'username': '',
            'password': ''
        },
        'source_channel': 'test_source',
        'target_channel': ['test_target1', 'test_target2'],
        'message_range': {
            'start_id': 1,
            'end_id': 10
        },
        'message_interval': 0.1,
        'session_name': 'test_session',
        'hide_author': True
    }

@pytest.fixture
def mock_client():
    client = MagicMock(spec=TelegramClient)
    client.connect = MagicMock(return_value=None)
    client.is_user_authorized = MagicMock(return_value=True)
    client.disconnect = MagicMock(return_value=None)
    return client

@pytest.mark.asyncio
async def test_config_validator(config):
    # 测试配置验证
    validated_config = await ConfigValidator.validate_config(config)
    assert validated_config == config

    # 测试无效配置
    invalid_config = config.copy()
    invalid_config['api_id'] = ''
    with pytest.raises(ValueError):
        await ConfigValidator.validate_config(invalid_config)

@pytest.mark.asyncio
async def test_telegram_client_manager(config, mock_client):
    with patch('telethon.TelegramClient', return_value=mock_client):
        client_manager = TelegramClientManager(config)
        await client_manager.connect_and_authorize()
        
        assert client_manager.client is not None
        assert client_manager.client.connect.called
        assert client_manager.client.is_user_authorized.called

@pytest.mark.asyncio
async def test_message_collector(mock_client):
    collector = MessageCollector(mock_client)
    
    # 模拟消息
    mock_message = MagicMock(spec=Message)
    mock_message.id = 1
    mock_message.grouped_id = None
    mock_client.get_messages.return_value = [mock_message]
    
    # 测试获取消息范围
    start_id, end_id = await collector.get_message_range('test_channel', 1, 10)
    assert start_id == 1
    assert end_id == 10
    
    # 测试收集消息
    messages = await collector.collect_messages('test_channel', 1, 10)
    assert len(messages) == 1
    assert messages[0].id == 1

@pytest.mark.asyncio
async def test_message_handler(config, mock_client):
    handler = MessageHandler(mock_client, config)
    
    # 模拟消息
    mock_message = MagicMock(spec=Message)
    mock_message.media = None
    mock_message.message = 'test message'
    
    # 测试发送消息
    success = await handler.send_message(mock_client, mock_message)
    assert success

def test_parse_channel_link():
    # 测试公开频道链接
    public_link = 'https://t.me/test_channel'
    assert parse_channel_link(public_link) == 'test_channel'
    
    # 测试私有频道链接
    private_link = 'https://t.me/c/1234567890/1'
    assert parse_channel_link(private_link) == '-1001234567890'
    
    # 测试无效链接
    invalid_link = 'invalid_link'
    assert parse_channel_link(invalid_link) == 'invalid_link'

@pytest.mark.asyncio
async def test_forwarder_app(config, mock_client):
    with patch('src.app.TelegramClientManager') as mock_client_manager:
        mock_client_manager.return_value.client = mock_client
        
        app = ForwarderApp()
        await app.initialize()
        
        assert app.config is not None
        assert app.client_manager is not None
        assert app.message_collector is not None
        assert app.message_handler is not None