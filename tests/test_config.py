import pytest
from unittest.mock import patch, mock_open
from src.config import ConfigManager

@pytest.mark.asyncio
async def test_load_config_success(mock_config):
    """测试成功加载配置文件"""
    with patch('builtins.open', mock_open(read_data='{}')):
        with patch('json.load', return_value=mock_config):
            config = await ConfigManager.load_config()
            assert config == mock_config
            assert config['api_id'] == '123456'
            assert config['api_hash'] == 'test_hash'

@pytest.mark.asyncio
async def test_load_config_file_not_found():
    """测试配置文件不存在的情况"""
    with patch('builtins.open', mock_open()) as mock_file:
        mock_file.side_effect = FileNotFoundError()
        with pytest.raises(FileNotFoundError):
            await ConfigManager.load_config()

@pytest.mark.asyncio
async def test_load_config_invalid_json():
    """测试配置文件JSON格式无效的情况"""
    with patch('builtins.open', mock_open(read_data='invalid json')):
        with pytest.raises(Exception):
            await ConfigManager.load_config()

@pytest.mark.asyncio
async def test_config_required_fields(mock_config):
    """测试配置文件必填字段"""
    with patch('builtins.open', mock_open(read_data='{}')):
        with patch('json.load', return_value=mock_config):
            config = await ConfigManager.load_config()
            assert 'api_id' in config
            assert 'api_hash' in config
            assert 'session_name' in config
            assert 'source_channel' in config
            assert 'target_channel' in config
            assert 'message_range' in config
            assert 'message_interval' in config
            assert 'proxy' in config