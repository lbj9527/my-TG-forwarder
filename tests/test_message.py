import pytest
from unittest.mock import AsyncMock, MagicMock
from telethon.errors import FloodWaitError, ChannelPrivateError
from src.message import MessageCollector, MessageHandler

@pytest.mark.asyncio
async def test_get_entity_success(mock_telegram_client):
    """测试成功获取频道实体"""
    collector = MessageCollector(mock_telegram_client)
    channel_id = '@test_channel'
    mock_telegram_client.get_entity = AsyncMock()
    
    await collector.get_entity(channel_id)
    mock_telegram_client.get_entity.assert_called_once_with(channel_id)

@pytest.mark.asyncio
async def test_get_entity_failure(mock_telegram_client):
    """测试获取频道实体失败"""
    collector = MessageCollector(mock_telegram_client)
    channel_id = '@test_channel'
    mock_telegram_client.get_entity = AsyncMock(side_effect=Exception('测试错误'))
    
    with pytest.raises(Exception):
        await collector.get_entity(channel_id)

@pytest.mark.asyncio
async def test_get_message_range_with_end_id(mock_telegram_client):
    """测试获取指定范围的消息ID"""
    collector = MessageCollector(mock_telegram_client)
    source_channel = '@test_channel'
    start_id = 1
    end_id = 10
    
    mock_telegram_client.get_entity = AsyncMock()
    actual_start, actual_end = await collector.get_message_range(source_channel, start_id, end_id)
    
    assert actual_start == start_id
    assert actual_end == end_id

@pytest.mark.asyncio
async def test_get_message_range_latest(mock_telegram_client):
    """测试获取最新消息范围"""
    collector = MessageCollector(mock_telegram_client)
    source_channel = '@test_channel'
    start_id = 1
    end_id = 0
    latest_message_id = 100
    
    mock_telegram_client.get_entity = AsyncMock()
    mock_telegram_client.get_messages = AsyncMock(return_value=[MagicMock(id=latest_message_id)])
    
    actual_start, actual_end = await collector.get_message_range(source_channel, start_id, end_id)
    
    assert actual_start == start_id
    assert actual_end == latest_message_id

@pytest.mark.asyncio
async def test_collect_messages_success(mock_telegram_client):
    """测试成功收集消息"""
    collector = MessageCollector(mock_telegram_client)
    source_channel = '@test_channel'
    start_id = 1
    end_id = 3
    
    mock_messages = [
        MagicMock(id=1, grouped_id=None, action=None),
        MagicMock(id=2, grouped_id=None, action=None),
        MagicMock(id=3, grouped_id=None, action=None)
    ]
    
    mock_telegram_client.get_entity = AsyncMock()
    mock_telegram_client.get_messages = AsyncMock(return_value=mock_messages)
    
    messages = await collector.collect_messages(source_channel, start_id, end_id)
    
    assert len(messages) == 3
    assert all(msg.id in [1, 2, 3] for msg in messages)

@pytest.mark.asyncio
async def test_collect_messages_with_media_group(mock_telegram_client):
    """测试收集媒体组消息"""
    collector = MessageCollector(mock_telegram_client)
    source_channel = '@test_channel'
    start_id = 1
    end_id = 3
    
    group_id = 12345
    mock_messages = [
        MagicMock(id=1, grouped_id=group_id, action=None),
        MagicMock(id=2, grouped_id=group_id, action=None),
        MagicMock(id=3, grouped_id=None, action=None)
    ]
    
    mock_telegram_client.get_entity = AsyncMock()
    mock_telegram_client.get_messages = AsyncMock(return_value=mock_messages)
    
    messages = await collector.collect_messages(source_channel, start_id, end_id)
    
    assert len(messages) == 2  # 1个媒体组和1个单独消息
    assert isinstance(messages[0], list)  # 第一个元素应该是媒体组列表
    assert len(messages[0]) == 2  # 媒体组包含2条消息

@pytest.mark.asyncio
async def test_send_message_success(mock_telegram_client, mock_config):
    """测试成功发送消息"""
    handler = MessageHandler(mock_telegram_client, mock_config)
    target_entity = MagicMock()
    message = MagicMock()
    
    await handler.send_message(target_entity, message)
    
    mock_telegram_client.forward_messages.assert_called_once_with(target_entity, message)

@pytest.mark.asyncio
async def test_send_message_flood_wait(mock_telegram_client, mock_config):
    """测试发送消息触发频率限制"""
    handler = MessageHandler(mock_telegram_client, mock_config)
    target_entity = MagicMock()
    message = MagicMock()
    
    # 模拟第一次调用触发频率限制，第二次调用成功
    mock_telegram_client.forward_messages = AsyncMock(
        side_effect=[FloodWaitError(5), None]
    )
    
    await handler.send_message(target_entity, message)
    
    assert mock_telegram_client.forward_messages.call_count == 2

@pytest.mark.asyncio
async def test_send_message_channel_private(mock_telegram_client, mock_config):
    """测试发送消息到私有频道失败"""
    handler = MessageHandler(mock_telegram_client, mock_config)
    target_entity = MagicMock()
    message = MagicMock()
    
    mock_telegram_client.forward_messages = AsyncMock(
        side_effect=ChannelPrivateError('无法访问私有频道')
    )
    
    with pytest.raises(ChannelPrivateError):
        await handler.send_message(target_entity, message)