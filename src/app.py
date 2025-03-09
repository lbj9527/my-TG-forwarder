from typing import Dict, Any, List, Union, Optional
from loguru import logger
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError
from .config import ConfigManager
from .client import TelegramClientManager
from .message import MessageCollector, MessageHandler
from .utils import parse_channel_link

class ForwarderApp:
    """Telegram消息转发应用类，负责协调和管理整个应用的功能"""
    
    def __init__(self):
        self.config: Optional[Dict[str, Any]] = None
        self.client_manager: Optional[TelegramClientManager] = None
        self.message_collector: Optional[MessageCollector] = None
        self.message_handler: Optional[MessageHandler] = None
        self.source_channel: Optional[str] = None
        self.target_channels: List[str] = []
        self.message_range: Optional[Dict[str, int]] = None

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
            if client is None:
                raise ValueError("TelegramClient实例不能为None")
            
            # 初始化消息处理器
            self.message_handler = MessageHandler(client, self.config)
            
            # 初始化消息收集器
            self.message_collector = MessageCollector(client)
            
            # 设置频道信息并解析频道链接
            self.source_channel = parse_channel_link(self.config['source_channel'])
            
            # 解析目标频道链接
            if isinstance(self.config['target_channel'], str):
                parsed_channel = parse_channel_link(self.config['target_channel'])
                self.target_channels = [parsed_channel] if parsed_channel else []
            else:
                self.target_channels = []
                for channel in self.config['target_channel']:
                    parsed_channel = parse_channel_link(channel)
                    if parsed_channel:
                        self.target_channels.append(parsed_channel)
            
            # 设置消息范围
            self.message_range = self.config['message_range']
            logger.info("应用初始化完成")
        except Exception as e:
            logger.error(f"应用初始化失败: {e}")
            raise

    async def run(self) -> None:
        """运行转发任务"""
        try:
            if self.source_channel is None:
                logger.error("源频道未设置")
                return
                
            # 检查message_range是否为None
            if self.message_range is None:
                logger.error("消息范围未设置")
                return
                
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
            total_messages = len(messages)
            total_targets = len(target_entities)
            successful_forwards = 0
            
            for i, message in enumerate(messages):
                logger.info(f"正在转发第 {i+1}/{total_messages} 条消息到所有目标频道...")
                
                # 预先下载媒体文件，只下载一次
                media_files = None
                caption = None
                is_protected = False
                try:
                    # 检查是否需要预先下载媒体文件
                    try:
                        # 尝试向第一个目标频道转发以检查是否是受保护的频道
                        first_target = next(iter(target_entities.values()))
                        test_message = message
                        await self.client_manager.client.forward_messages(first_target, test_message, drop_author=self.config.get('hide_author', True))
                        # 记录第一个目标频道的转发成功
                        successful_forwards += 1
                        logger.info(f"消息 {i+1}/{total_messages} 成功转发到频道 {next(iter(target_entities.keys()))}")
                    except Exception as e:
                        if "You can't forward messages from a protected chat" in str(e):
                            # 如果是受保护的频道，预先下载媒体文件
                            is_protected = True
                            media_files, caption = await self.message_handler.download_media_files(message)
                            logger.info(f"已预先下载媒体文件，准备发送到所有目标频道")
                        else:
                            # 其他错误，记录失败
                            logger.error(f"向第一个目标频道转发消息时出错: {e}")
                except Exception as e:
                    logger.error(f"预处理消息时出错: {e}")
                
                # 转发到剩余的目标频道
                remaining_targets = list(target_entities.items())
                if not is_protected:
                    # 如果不是受保护的频道，跳过第一个已经转发成功的目标
                    remaining_targets = remaining_targets[1:]
                
                for target_channel, target_entity in remaining_targets:
                    try:
                        if is_protected:
                            success = await self.message_handler.send_message(target_entity, message, media_files, caption)
                        else:
                            success = await self.client_manager.client.forward_messages(target_entity, message, drop_author=self.config.get('hide_author', True)) is not None
                        
                        if success:
                            successful_forwards += 1
                            logger.info(f"消息 {i+1}/{total_messages} 成功转发到频道 {target_channel}")
                        else:
                            logger.error(f"消息 {i+1}/{total_messages} 转发到频道 {target_channel} 失败")
                    except Exception as e:
                        logger.error(f"向频道 {target_channel} 转发消息 {i+1} 时出错: {e}")
                
                # 清理已下载的媒体文件
                if media_files:
                    for temp_file in media_files:
                        try:
                            import os
                            os.remove(temp_file)
                        except Exception as e:
                            logger.error(f"清理临时文件失败: {e}")
            
            # 只有当所有消息都成功转发时才显示完成日志
            expected_forwards = total_messages * total_targets
            if successful_forwards == expected_forwards:
                logger.info("所有转发任务完成")
            else:
                logger.warning(f"转发任务结束，但有 {expected_forwards - successful_forwards} 条消息转发失败")
        except Exception as e:
            logger.error(f"运行转发任务失败: {e}")
            raise

    async def close(self) -> None:
        """关闭应用"""
        if self.client_manager is not None and self.client_manager.client is not None:
            await self.client_manager.client.disconnect()
            logger.info("已断开Telegram客户端连接")