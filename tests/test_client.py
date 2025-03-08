import pytest
from unittest.mock import patch, AsyncMock
from src.client import TelegramClientManager

@pytest.mark.asyncio
async def test_setup_proxy_enabled(mock_config):
    """测试启用代理配置"""
    mock_config['proxy']['enabled'] = True
    client_manager = TelegramClientManager(mock_config)
    proxy_config = await client_manager.setup_proxy()
    
    assert proxy_config is not None
    assert proxy_config['addr'] == mock_config['proxy']['host']
    assert proxy_config['port'] == mock_config['proxy']['port']

@pytest.mark.asyncio
async def test_setup_proxy_disabled(mock_config):
    """测试禁用代理配置"""
    mock_config['proxy']['enabled'] = False
    client_manager = TelegramClientManager(mock_config)
    proxy_config = await client_manager.setup_proxy()
    
    assert proxy_config is None

@pytest.mark.asyncio
async def test_create_client(mock_config):
    """测试创建客户端实例"""
    with patch('telethon.TelegramClient') as mock_client:
        client_manager = TelegramClientManager(mock_config)
        await client_manager.create_client()
        
        mock_client.assert_called_once_with(
            mock_config['session_name'],
            mock_config['api_id'],
            mock_config['api_hash'],
            proxy=None
        )

@pytest.mark.asyncio
async def test_connect_and_authorize_existing_session(mock_config, mock_telegram_client):
    """测试使用现有会话连接和授权"""
    client_manager = TelegramClientManager(mock_config)
    client_manager.client = mock_telegram_client
    
    await client_manager.connect_and_authorize()
    
    mock_telegram_client.connect.assert_called_once()
    mock_telegram_client.is_user_authorized.assert_called_once()
    mock_telegram_client.send_code_request.assert_not_called()

@pytest.mark.asyncio
async def test_connect_and_authorize_new_session(mock_config, mock_telegram_client):
    """测试新会话的连接和授权"""
    mock_telegram_client.is_user_authorized.return_value = False
    client_manager = TelegramClientManager(mock_config)
    client_manager.client = mock_telegram_client
    
    with patch('builtins.input', side_effect=['123456789', '12345']):
        await client_manager.connect_and_authorize()
    
    mock_telegram_client.connect.assert_called_once()
    mock_telegram_client.is_user_authorized.assert_called_once()
    mock_telegram_client.send_code_request.assert_called_once()
    mock_telegram_client.sign_in.assert_called_once()

@pytest.mark.asyncio
async def test_disconnect(mock_config, mock_telegram_client):
    """测试断开客户端连接"""
    client_manager = TelegramClientManager(mock_config)
    client_manager.client = mock_telegram_client
    
    await client_manager.disconnect()
    
    mock_telegram_client.disconnect.assert_called_once()