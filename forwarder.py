import json
import asyncio
import time
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
from loguru import logger
import python_socks
from typing import List, Dict, Union, Optional, Any, Tuple

# 配置日志
logger.add("forwarder.log", rotation="10 MB", compression="zip", level="INFO")


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

        if 'target_channel' not in config:
            errors.append("缺少target_channel配置")
        elif isinstance(config['target_channel'], str):
            if not config['target_channel']:
                errors.append("target_channel为空")
        elif isinstance(config['target_channel'], list):
            if not config['target_channel']:
                errors.append("target_channel数组为空")
            for idx, channel in enumerate(config['target_channel']):
                if not isinstance(channel, str) or not channel:
                    errors.append(f"target_channel数组中第{idx+1}个元素无效或为空")
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


class MessageHandler:
    """消息处理类，负责处理单条消息和媒体组"""
    
    def __init__(self, client: TelegramClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.message_interval = config['message_interval']

    @staticmethod
    def get_channel_identifier(channel) -> str:
        """获取频道的标识符"""
        return getattr(channel, 'username', None) or f'private_{channel.id}'

    async def send_media_group(self, target_channel, message_group) -> None:
        """发送媒体组消息"""
        grouped_id = message_group[0].grouped_id
        media_files = [msg.media for msg in message_group]
        caption = message_group[0].message if message_group[0].message else None
        
        try:
            await self.client.send_file(
                target_channel,
                file=media_files,
                caption=caption
            )
            logger.info(f"成功发送媒体组消息 Grouped ID: {grouped_id} 到频道: {self.get_channel_identifier(target_channel)}")
        except FloodWaitError as e:
            logger.warning(f"触发限制，等待 {e.seconds} 秒")
            await asyncio.sleep(e.seconds)
            # 递归重试
            await self.send_media_group(target_channel, message_group)
        except ChatAdminRequiredError:
            logger.error(f"发送媒体组消息失败: 需要管理员权限 Grouped ID: {grouped_id} 到频道: {self.get_channel_identifier(target_channel)}")
            raise
        except Exception as e:
            logger.error(f"发送媒体组消息失败 Grouped ID: {grouped_id} 到频道: {self.get_channel_identifier(target_channel)}, 错误: {e}")
            raise

    async def send_single_message(self, target_channel, message) -> None:
        """发送单条消息"""
        try:
            media_type = "文本"
            if message.media:
                if hasattr(message.media, 'photo'):
                    media_type = "图片"
                elif hasattr(message.media, 'document'):
                    media_type = "视频/文件"
                
                await self.client.send_file(
                    target_channel,
                    file=message.media,
                    caption=message.message
                )
            else:
                await self.client.send_message(
                    target_channel,
                    message=message.message
                )
            logger.info(f"成功发送{media_type}消息 ID: {message.id} 到频道: {self.get_channel_identifier(target_channel)}")
        except FloodWaitError as e:
            logger.warning(f"触发限制，等待 {e.seconds} 秒")
            await asyncio.sleep(e.seconds)
            # 递归重试
            await self.send_single_message(target_channel, message)
        except ChatAdminRequiredError:
            logger.error(f"发送消息失败: 需要管理员权限 ID: {message.id} 到频道: {self.get_channel_identifier(target_channel)}")
            raise
        except Exception as e:
            logger.error(f"发送消息失败 ID: {message.id} 到频道: {self.get_channel_identifier(target_channel)}, 错误: {e}")
            raise

    async def send_message(self, target_channel, message) -> None:
        """发送消息（单条或媒体组）"""
        if isinstance(message, list):
            await self.send_media_group(target_channel, message)
        else:
            await self.send_single_message(target_channel, message)
        
        # 发送后等待指定的间隔时间
        await asyncio.sleep(self.message_interval)


class MessageCollector:
    """消息收集类，负责收集需要转发的消息"""
    
    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_message_range(self, source_channel, start_id: int, end_id: int) -> Tuple[int, int]:
        """获取消息范围，确定实际的起始和结束消息ID"""
        try:
            # 获取频道信息
            entity = await self.client.get_entity(source_channel)
            logger.info(f"成功获取频道信息: {getattr(entity, 'username', None) or entity.id}")
            
            # 如果end_id为0，表示获取到最新消息
            if end_id == 0:
                # 获取最新消息ID
                messages = await self.client.get_messages(entity, limit=1)
                if not messages:
                    logger.warning("未找到任何消息")
                    return start_id, start_id
                end_id = messages[0].id
                logger.info(f"最新消息ID: {end_id}")
            
            # 检查start_id和end_id的大小关系
            if start_id > end_id:
                error_msg = f"起始ID({start_id})大于结束ID({end_id})，请确保end_id大于start_id，或将end_id设置为0以获取最新消息"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            return start_id, end_id
        except ChannelPrivateError:
            logger.error(f"无法访问私有频道: {source_channel}")
            raise
        except Exception as e:
            logger.error(f"获取消息范围失败: {e}")
            raise
    
    async def collect_messages(self, source_channel, start_id: int, end_id: int) -> List[Union[List, Any]]:
        """收集指定范围内的消息"""
        try:
            # 获取频道实体
            entity = await self.client.get_entity(source_channel)
            logger.info(f"开始收集消息，范围: {start_id} - {end_id}")
            
            # 存储所有消息
            all_messages = []
            # 存储媒体组消息的临时字典
            media_groups = {}
            
            # 批量获取消息，每次获取100条
            batch_size = 100
            current_id = start_id
            
            while current_id <= end_id:
                # 计算本批次的结束ID
                batch_end = min(current_id + batch_size - 1, end_id)
                logger.info(f"获取消息批次: {current_id} - {batch_end}")
                
                # 获取消息批次
                messages = await self.client.get_messages(
                    entity,
                    min_id=current_id - 1,  # min_id是不包含的，所以减1
                    max_id=batch_end + 1,   # max_id是不包含的，所以加1
                    limit=batch_size
                )
                
                if not messages:
                    logger.warning(f"未找到ID范围 {current_id} - {batch_end} 内的消息")
                    current_id = batch_end + 1
                    continue
                
                # 处理获取到的消息
                for message in messages:
                    # 跳过空消息或服务消息
                    if message is None or message.action is not None:
                        continue
                    
                    # 处理媒体组消息
                    if message.grouped_id:
                        if message.grouped_id not in media_groups:
                            media_groups[message.grouped_id] = []
                        media_groups[message.grouped_id].append(message)
                    else:
                        all_messages.append(message)
                
                # 更新当前ID为下一批次的起始ID
                current_id = batch_end + 1
                
                # 添加短暂延迟，避免请求过于频繁
                await asyncio.sleep(0.5)
            
            # 将媒体组消息添加到结果列表中
            for group_id, group_messages in media_groups.items():
                # 按照消息ID排序，确保顺序正确
                group_messages.sort(key=lambda x: x.id)
                all_messages.append(group_messages)
            
            # 按照消息ID或媒体组第一条消息的ID排序
            all_messages.sort(key=lambda x: x[0].id if isinstance(x, list) else x.id)
            
            logger.info(f"成功收集 {len(all_messages)} 条消息/媒体组")
            return all_messages
        except ChannelPrivateError:
            logger.error(f"无法访问私有频道: {source_channel}")
            raise
        except Exception as e:
            logger.error(f"收集消息失败: {e}")
            raise


class ForwarderApp:
    """转发应用类，负责协调各个组件完成转发任务"""
    
    def __init__(self):
        self.config = None
        self.client_manager = None
        self.client = None
        self.message_collector = None
        self.message_handler = None
    
    async def initialize(self) -> None:
        """初始化应用"""
        try:
            # 加载配置
            logger.info("开始加载配置文件...")
            self.config = await ConfigManager.load_config()
            logger.info("配置文件加载成功")
            
            # 创建客户端管理器
            self.client_manager = TelegramClientManager(self.config)
            
            # 创建并连接客户端
            logger.info("开始创建Telegram客户端...")
            self.client = await self.client_manager.create_client()
            
            # 连接并授权
            logger.info("开始连接并授权...")
            await self.client_manager.connect_and_authorize()
            
            # 创建消息收集器和处理器
            self.message_collector = MessageCollector(self.client)
            self.message_handler = MessageHandler(self.client, self.config)
            
            logger.info("应用初始化完成")
        except Exception as e:
            logger.error(f"初始化应用失败: {e}")
            raise
    
    async def run(self) -> None:
        """运行转发任务"""
        try:
            # 获取源频道和目标频道
            source_channel = self.config['source_channel']
            target_channels = self.config['target_channel']
            if isinstance(target_channels, str):
                target_channels = [target_channels]
            
            # 获取消息范围
            start_id = self.config['message_range']['start_id']
            end_id = self.config['message_range']['end_id']
            
            # 确定实际的消息范围
            logger.info(f"开始确定消息范围，配置范围: {start_id} - {end_id}")
            start_id, end_id = await self.message_collector.get_message_range(source_channel, start_id, end_id)
            logger.info(f"实际消息范围: {start_id} - {end_id}")
            
            # 收集消息
            logger.info(f"开始从频道 {source_channel} 收集消息...")
            messages = await self.message_collector.collect_messages(source_channel, start_id, end_id)
            logger.info(f"共收集到 {len(messages)} 条消息/媒体组")
            
            # 如果没有消息，直接返回
            if not messages:
                logger.warning("没有找到需要转发的消息")
                return
            
            # 获取所有目标频道实体
            target_entities = {}
            for target_channel in target_channels:
                try:
                    target_entity = await self.client.get_entity(target_channel)
                    target_entities[target_channel] = target_entity
                    logger.info(f"成功获取频道实体: {target_channel}")
                except ChannelPrivateError:
                    logger.error(f"无法访问私有频道: {target_channel}，跳过此频道")
                except ChatAdminRequiredError:
                    logger.error(f"需要管理员权限才能在频道 {target_channel} 发送消息，跳过此频道")
                except Exception as e:
                    logger.error(f"获取频道 {target_channel} 实体时出错: {e}，跳过此频道")
            
            # 如果没有有效的目标频道，直接返回
            if not target_entities:
                logger.warning("没有有效的目标频道，转发任务终止")
                return
            
            # 按消息循环，同时转发到所有目标频道
            for i, message in enumerate(messages):
                logger.info(f"正在转发第 {i+1}/{len(messages)} 条消息到所有目标频道...")
                
                # 同时转发到所有目标频道
                for target_channel, target_entity in target_entities.items():
                    try:
                        await self.message_handler.send_message(target_entity, message)
                        logger.info(f"消息 {i+1}/{len(messages)} 成功转发到频道 {target_channel}")
                    except Exception as e:
                        logger.error(f"向频道 {target_channel} 转发消息 {i+1} 时出错: {e}")
            
            logger.info("所有转发任务完成")
        except Exception as e:
            logger.error(f"运行转发任务失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭应用"""
        if self.client:
            await self.client.disconnect()
            logger.info("已断开Telegram客户端连接")


async def main() -> None:
    """主函数"""
    app = ForwarderApp()
    try:
        # 初始化应用
        await app.initialize()
        
        # 运行转发任务
        await app.run()
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
    finally:
        # 确保关闭应用
        await app.close()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())