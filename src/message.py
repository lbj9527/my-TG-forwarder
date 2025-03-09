from typing import List, Union, Any, Optional, Dict
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel, PeerChannel
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
from loguru import logger
import asyncio
import time
import os
import tempfile

class MessageCollector:
    """消息收集器类，负责收集和处理消息"""
    
    def __init__(self, client: TelegramClient):
        if client is None:
            raise ValueError("TelegramClient实例不能为None")
        self.client = client

    async def get_entity(self, channel_id: str):
        """获取频道实体"""
        try:
            # 如果是数字ID（私有频道），转换为整数
            if channel_id and channel_id.startswith('-100') and channel_id[4:].isdigit():
                # 去掉'-100'前缀并转换为整数
                peer_id = int(channel_id[4:])
                # 使用InputPeerChannel构造正确的实体引用
                return await self.client.get_entity(InputPeerChannel(peer_id, 0))
            # 否则按原样处理（用户名或其他格式）
            return await self.client.get_entity(channel_id)
        except Exception as e:
            logger.error(f"获取频道实体失败: {e}")
            raise

    async def get_message_range(self, source_channel: Union[str, None], start_id: int, end_id: int) -> tuple[int, int]:
        if source_channel is None:
            raise ValueError("源频道不能为None")
        """获取实际的消息范围"""
        try:
            # 使用get_entity方法获取实体，而不是直接使用source_channel
            entity = await self.get_entity(source_channel)
            if end_id == 0:
                # 获取最新消息的ID
                messages = await self.client.get_messages(entity, limit=1)
                if not messages:
                    raise ValueError("无法获取最新消息ID")
                # 确保messages是一个列表且有元素
                first_message = messages[0] if isinstance(messages, (list, tuple)) else messages
                end_id = first_message.id
                logger.info(f"获取到最新消息ID: {end_id}")
            return start_id, end_id
        except Exception as e:
            logger.error(f"获取消息范围失败: {e}")
            raise

    async def collect_messages(self, source_channel, start_id: int, end_id: int) -> List[Union[List, Any]]:
        """收集指定范围内的消息"""
        try:
            # 获取频道实体
            entity = await self.get_entity(source_channel)
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
                
                # 确保messages不为None且可迭代
                if messages is None:
                    logger.warning(f"批次 {current_id} - {batch_end} 未返回任何消息")
                    messages = []
                
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
        if client is None:
            raise ValueError("TelegramClient实例不能为None")
        self.client = client
        self.config = config
        # 创建临时目录用于存储下载的文件
        import os
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'tmp_file')
        os.makedirs(self.temp_dir, exist_ok=True)

    async def download_progress_callback(self, current: int, total: int) -> None:
        """显示下载进度的回调函数"""
        print(f'下载进度: {current * 100 / total:.1f}%')

    async def progress_callback(self, current: int, total: int) -> None:
        """显示上传进度的回调函数"""
        print(f'上传进度: {current * 100 / total:.1f}%')

    async def download_media_files(self, message: Union[Any, List[Any]]) -> tuple[list, Optional[str]]:
        """下载媒体文件并返回文件路径列表和说明文字"""
        media_files = []
        caption = None
        
        try:
            if isinstance(message, list):
                # 处理媒体组消息
                for msg in message:
                    if msg.media:
                        # 为每个文件生成临时文件路径，包含扩展名
                        file_name = f'media_{msg.id}'
                        if hasattr(msg.media, 'document') and msg.media.document.mime_type:
                            ext = msg.media.document.mime_type.split('/')[-1]
                            file_name = f'{file_name}.{ext}'
                        temp_path = os.path.join(self.temp_dir, file_name)
                        # 下载媒体文件
                        downloaded_file = await self.client.download_media(
                            msg.media,
                            temp_path,
                            progress_callback=self.download_progress_callback
                        )
                        if downloaded_file and os.path.exists(downloaded_file):
                            media_files.append(downloaded_file)
                        else:
                            logger.error(f"文件下载失败: {temp_path}")
                caption = message[0].message if message[0].message else None
            else:
                # 处理单条消息
                if message.media:
                    temp_path = os.path.join(self.temp_dir, f'media_{message.id}')
                    downloaded_file = await self.client.download_media(
                        message.media,
                        temp_path,
                        progress_callback=self.download_progress_callback
                    )
                    if downloaded_file and os.path.exists(downloaded_file):
                        media_files.append(downloaded_file)
                    caption = message.message
        except Exception as e:
            logger.error(f"下载媒体文件失败: {e}")
            # 清理已下载的文件
            for temp_file in media_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise
        
        return media_files, caption

    async def send_message(self, target_entity: Any, message: Union[Any, List[Any]], media_files: List[str] = None, caption: Optional[str] = None) -> bool:
        """发送单条消息或媒体组消息"""
        try:
            # 从配置中获取hide_author设置，如果不存在则默认为True
            hide_author = self.config.get('hide_author', True)
            local_media_files = media_files or []
            local_caption = caption
            need_cleanup = False
            
            # 先尝试直接转发
            try:
                await self.client.forward_messages(target_entity, message, drop_author=hide_author)
                return True
            except Exception as e:
                # 只处理受保护频道的错误，其他错误直接抛出
                if "You can't forward messages from a protected chat" in str(e):
                    logger.info("检测到受保护频道，尝试使用备选发送方案")
                    # 如果是受保护的频道，且没有提供媒体文件，则下载文件
                    if not local_media_files:
                        local_media_files, local_caption = await self.download_media_files(message)
                        need_cleanup = True  # 标记这些文件需要在此方法内清理
                    
                    if local_media_files:
                        try:
                            # 发送媒体文件
                            await self.client.send_file(
                                target_entity,
                                file=local_media_files,
                                caption=local_caption,
                                allow_cache=True,
                                progress_callback=self.progress_callback
                            )
                            logger.info("使用send_file成功发送媒体消息")
                            return True
                        except Exception as inner_e:
                            logger.error(f"使用send_file发送媒体消息失败: {inner_e}")
                            # 如果是媒体组消息，尝试逐个发送
                            if isinstance(message, list):
                                success = True
                                for i, msg in enumerate(message):
                                    try:
                                        single_caption = msg.message if i == 0 else None
                                        await self.client.send_file(
                                            target_entity,
                                            file=msg.media,
                                            caption=single_caption,
                                            allow_cache=True
                                        )
                                        await asyncio.sleep(0.5)
                                    except Exception as single_e:
                                        logger.error(f"发送单个媒体文件失败: {single_e}")
                                        success = False
                                return success
                            return False
                    else:
                        # 纯文本消息
                        if not isinstance(message, list):
                            await self.client.send_message(
                                target_entity,
                                message=message.message
                            )
                            logger.info("成功发送纯文本消息")
                            return True
                        return False  # 对于媒体组消息，如果没有媒体文件，则返回失败
                else:
                    # 如果是其他错误，记录详细信息并抛出
                    logger.error(f"转发消息失败，错误类型: {type(e).__name__}, 错误信息: {str(e)}")
                    raise
        except FloodWaitError as e:
            logger.warning(f"触发频率限制，等待 {e.seconds} 秒")
            await asyncio.sleep(e.seconds)
            # 重试发送
            return await self.send_message(target_entity, message, local_media_files, local_caption)
        except Exception as e:
            logger.error(f"转发消息失败: {e}")
            return False
        finally:
            # 只有当这些文件是在此方法内下载的，才在此方法内清理
            if need_cleanup and local_media_files:
                for temp_file in local_media_files:
                    try:
                        os.remove(temp_file)
                    except:
                        pass