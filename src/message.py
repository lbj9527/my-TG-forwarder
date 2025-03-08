from typing import List, Union, Any, Optional, Dict
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel, PeerChannel
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
from loguru import logger
import asyncio
import time

class MessageCollector:
    """消息收集器类，负责收集和处理消息"""
    
    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_entity(self, channel_id: str):
        """获取频道实体"""
        try:
            return await self.client.get_entity(channel_id)
        except Exception as e:
            logger.error(f"获取频道实体失败: {e}")
            raise

    async def get_message_range(self, source_channel: str, start_id: int, end_id: int) -> tuple[int, int]:
        """获取实际的消息范围"""
        try:
            entity = await self.client.get_entity(source_channel)
            if end_id == 0:
                # 获取最新消息的ID
                messages = await self.client.get_messages(entity, limit=1)
                if not messages:
                    raise ValueError("无法获取最新消息ID")
                end_id = messages[0].id
                logger.info(f"获取到最新消息ID: {end_id}")
            return start_id, end_id
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
                    ids=list(range(current_id, batch_end + 1))
                )
                
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

class MessageHandler:
    """消息处理器类，负责转发消息"""
    
    def __init__(self, client: TelegramClient, config: Dict[str, Any]):
        self.client = client
        self.config = config

    async def send_message(self, target_entity: Any, message: Union[Any, List[Any]]) -> None:
        """发送单条消息或媒体组消息"""
        try:
            if isinstance(message, list):
                # 转发媒体组消息
                await self.client.forward_messages(target_entity, message)
            else:
                # 转发单条消息
                await self.client.forward_messages(target_entity, message)
            
            # 添加延迟，避免触发限制
            await asyncio.sleep(self.config['message_interval'])
        except FloodWaitError as e:
            logger.warning(f"触发频率限制，等待 {e.seconds} 秒")
            await asyncio.sleep(e.seconds)
            # 重试发送
            await self.send_message(target_entity, message)
        except Exception as e:
            logger.error(f"转发消息失败: {e}")
            raise