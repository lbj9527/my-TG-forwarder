import json
from typing import Dict, Any, List
from loguru import logger

class ConfigValidator:
    """配置验证器类，负责验证和处理配置文件"""
    
    @staticmethod
    async def validate_api_credentials(config: Dict[str, Any]) -> List[str]:
        """验证API凭证"""
        errors = []
        if 'api_id' not in config or not config['api_id']:
            errors.append("缺少api_id或api_id为空")
        elif not isinstance(config['api_id'], (str, int)):
            errors.append("api_id必须是字符串或整数")
        
        if 'api_hash' not in config or not config['api_hash']:
            errors.append("缺少api_hash或api_hash为空")
        elif not isinstance(config['api_hash'], str):
            errors.append("api_hash必须是字符串")
        return errors

    @staticmethod
    async def validate_proxy_settings(config: Dict[str, Any]) -> List[str]:
        """验证代理设置"""
        errors = []
        if 'proxy' not in config:
            errors.append("缺少代理配置")
            return errors

        proxy = config['proxy']
        if not isinstance(proxy, dict):
            errors.append("代理配置必须是一个对象")
            return errors

        if 'enabled' not in proxy:
            errors.append("代理配置缺少enabled字段")
        elif not isinstance(proxy['enabled'], bool):
            errors.append("proxy.enabled必须是布尔值")

        if proxy['enabled']:
            if 'type' not in proxy or not proxy['type']:
                errors.append("代理配置缺少type字段或type为空")
            elif proxy['type'].lower() not in ['socks5', 'socks4']:
                errors.append("代理类型必须是socks5或socks4")

            if 'host' not in proxy or not proxy['host']:
                errors.append("代理配置缺少host字段或host为空")

            if 'port' not in proxy:
                errors.append("代理配置缺少port字段")
            elif not isinstance(proxy['port'], int) or proxy['port'] <= 0 or proxy['port'] > 65535:
                errors.append("代理端口必须是1-65535之间的整数")
        return errors

    @staticmethod
    async def validate_channel_settings(config: Dict[str, Any]) -> List[str]:
        """验证频道设置"""
        errors = []
        if 'source_channel' not in config or not config['source_channel']:
            errors.append("缺少source_channel或source_channel为空")
        elif isinstance(config['source_channel'], str):
            # 验证频道ID格式
            if config['source_channel'].startswith('-'):
                channel_id = config['source_channel'].lstrip('-')
                if not channel_id.isdigit():
                    errors.append("source_channel的频道ID格式无效")

        if 'target_channel' not in config:
            errors.append("缺少target_channel配置")
        elif isinstance(config['target_channel'], str):
            if not config['target_channel']:
                errors.append("target_channel为空")
            # 验证单个频道ID格式
            elif config['target_channel'].startswith('-'):
                channel_id = config['target_channel'].lstrip('-')
                if not channel_id.isdigit():
                    errors.append("target_channel的频道ID格式无效")
        elif isinstance(config['target_channel'], list):
            if not config['target_channel']:
                errors.append("target_channel数组为空")
            for idx, channel in enumerate(config['target_channel']):
                if not isinstance(channel, str) or not channel:
                    errors.append(f"target_channel数组中第{idx+1}个元素无效或为空")
                # 验证数组中的频道ID格式
                elif channel.startswith('-'):
                    channel_id = channel.lstrip('-')
                    if not channel_id.isdigit():
                        errors.append(f"target_channel数组中第{idx+1}个频道ID格式无效")
        else:
            errors.append("target_channel必须是字符串或字符串数组")
        return errors

    @staticmethod
    async def validate_message_range(config: Dict[str, Any]) -> List[str]:
        """验证消息范围设置"""
        errors = []
        if 'message_range' not in config:
            errors.append("缺少message_range配置")
            return errors

        message_range = config['message_range']
        if not isinstance(message_range, dict):
            errors.append("message_range必须是一个对象")
            return errors

        if 'start_id' not in message_range:
            errors.append("message_range缺少start_id字段")
        elif not isinstance(message_range['start_id'], int) or message_range['start_id'] < 0:
            errors.append("start_id必须是非负整数")

        if 'end_id' not in message_range:
            errors.append("message_range缺少end_id字段")
        elif not isinstance(message_range['end_id'], int) or message_range['end_id'] < 0:
            errors.append("end_id必须是非负整数")
        
        # 验证end_id必须大于start_id，除非end_id为0（表示获取到最新消息）
        if 'start_id' in message_range and 'end_id' in message_range:
            start_id = message_range['start_id']
            end_id = message_range['end_id']
            if end_id != 0 and end_id < start_id:
                errors.append(f"end_id({end_id})必须大于start_id({start_id})，或设置为0表示获取到最新消息")
        return errors

    @staticmethod
    async def validate_other_settings(config: Dict[str, Any]) -> List[str]:
        """验证其他设置"""
        errors = []
        if 'session_name' not in config or not config['session_name']:
            errors.append("缺少session_name或session_name为空")

        if 'message_interval' not in config:
            errors.append("缺少message_interval配置")
        elif not isinstance(config['message_interval'], (int, float)) or config['message_interval'] < 0:
            errors.append("message_interval必须是非负数")
        return errors

    @classmethod
    async def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证配置文件参数的有效性"""
        all_errors = []
        validation_tasks = [
            cls.validate_api_credentials(config),
            cls.validate_proxy_settings(config),
            cls.validate_channel_settings(config),
            cls.validate_message_range(config),
            cls.validate_other_settings(config)
        ]

        for task in validation_tasks:
            errors = await task
            all_errors.extend(errors)

        if all_errors:
            error_message = "\n".join(all_errors)
            logger.error(f"配置文件验证失败:\n{error_message}")
            raise ValueError(f"配置文件验证失败:\n{error_message}")

        return config


class ConfigManager:
    """配置管理类，负责加载和验证配置"""
    
    @staticmethod
    async def load_config() -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 验证配置
                return await ConfigValidator.validate_config(config)
        except FileNotFoundError:
            logger.error("配置文件不存在: config.json")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise