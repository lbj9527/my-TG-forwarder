from typing import Dict, Any, List, Union
from loguru import logger
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError
from .config import ConfigManager
from .client import TelegramClientManager
from .message import MessageCollector, MessageHandler

class ForwarderApp:
    """Telegram消息转发应用类，负责协调和管理整个应用的功能"""
    
    def __init__(self):
        self.config = None
        self.client_manager = None
        self.message_collector = None
        self.message_handler = None
        self.source_channel = None
        self.target_channels = None
        self.message_range = None

    async def initialize(self) -> None:
        """初始化应用"""
        try:
            # 加载配置
            self.config = await ConfigManager.load_config()
            
            # 初始化客户端管理器
            self.client_manager = TelegramClientManager(self.config)
            await self.client_manager.connect_and_authorize()
            
            # 获取客户端实例
            client = self.client_manager.client
            
            # 初始化消息处理器
            self.message_handler = MessageHandler(client, self.config)
            
            # 初始化消息收集器
            self.message_collector = MessageCollector(client)
            
            # 设置频道信息
            self.source_channel = self.config['source_channel']
            self.target_channels = (
                [self.config['target_channel']]
                if isinstance(self.config['target_channel'], str)
                else self.config['target_channel']
            )
            
            # 设置消息范围
            self.message_range = self.config['message_range']
            logger.info("应用初始化完成")
        except Exception as e:
            logger.error(f"应用初始化失败: {e}")
            raise

    async def run(self) -> None:
        """运行转发任务"""
        try:
            # 获取实际的消息范围
            start_id, end_id = await self.message_collector.get_message_range(
                self.source_channel,
                self.message_range['start_id'],
                self.message_range['end_id']
            )
            
            # 收集需要转发的消息
            messages = await self.message_collector.collect_messages(
                self.source_channel,
                start_id,
                end_id
            )
            
            if not messages:
                logger.warning("没有找到需要转发的消息")
                return
            
            # 获取源频道实体
            try:
                source_entity = await self.message_collector.get_entity(self.source_channel)
                logger.info(f"成功获取源频道实体: {self.source_channel}")
            except Exception as e:
                logger.error(f"获取源频道实体时出错: {e}")
                return
            
            # 获取目标频道实体
            target_entities = {}
            for target_channel in self.target_channels:
                try:
                    target_entity = await self.message_collector.get_entity(target_channel)
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
        if self.client_manager and self.client_manager.client:
            await self.client_manager.client.disconnect()
            logger.info("已断开Telegram客户端连接")