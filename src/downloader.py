from typing import Optional, BinaryIO, Callable, Union, List
from telethon import TelegramClient
from telethon.tl.types import Message, DocumentAttributeFilename
from loguru import logger
import os
import asyncio
from tqdm import tqdm
import humanize
import async_timeout

class TelegramDownloader:
    """高效的Telegram文件下载器"""
    
    def __init__(self, client: TelegramClient, temp_dir: str):
        """初始化下载器
        
        Args:
            client: TelegramClient实例
            temp_dir: 临时文件存储目录
        """
        self.client = client
        self.temp_dir = temp_dir
        self._chunk_size = 4 * 1024 * 1024  # 调整为4MB分块以提高性能
        self._download_timeout = 180  # 下载超时时间（秒）
        self._max_concurrent_downloads = 2  # 最大并发下载数
        self._semaphore = asyncio.Semaphore(self._max_concurrent_downloads)
        
    async def _create_progress_bar(self, total: int, desc: str) -> tqdm:
        """创建进度条"""
        return tqdm(
            total=total,
            desc=desc,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            dynamic_ncols=True
        )
        
    async def _download_file(self, message: Message, file_path: str) -> Optional[str]:
        """下载单个文件
        
        Args:
            message: Telegram消息对象
            file_path: 文件保存路径
            
        Returns:
            下载成功返回文件路径，失败返回None
        """
        try:
            # 使用信号量限制并发下载数量
            async with self._semaphore:
                if not message.media:
                    return None
                    
                # 获取文件大小
                file_size = message.media.document.size if hasattr(message.media, 'document') else 0
                human_size = humanize.naturalsize(file_size)
                
                # 创建进度条
                progress_bar = await self._create_progress_bar(
                    total=file_size,
                    desc=f'下载文件 ({human_size})'
                )
                
                # 使用异步方式下载，并设置超时
                async with async_timeout.timeout(self._download_timeout):
                    downloaded_file = await self.client.download_media(
                        message.media,
                        file_path,
                        progress_callback=lambda current, total: (
                            progress_bar.update(current - progress_bar.n)
                        )
                    )
                
                progress_bar.close()
                
                if downloaded_file and os.path.exists(downloaded_file):
                    logger.info(f'文件下载完成: {downloaded_file} ({human_size})')
                    return downloaded_file
                return None
                
        except asyncio.TimeoutError:
            logger.error(f'文件下载超时')
            if os.path.exists(file_path):
                os.remove(file_path)
            return None
        except Exception as e:
            logger.error(f'文件下载失败: {e}')
            if os.path.exists(file_path):
                os.remove(file_path)
            return None
            
    async def download_media_files(self, message: Union[Message, List[Message]]) -> tuple[list, Optional[str]]:
        """下载媒体文件
        
        Args:
            message: 单条消息或消息列表（媒体组）
            
        Returns:
            (media_files, caption): 下载的文件路径列表和消息文本
        """
        media_files = []
        caption = None
        
        try:
            if isinstance(message, list):
                # 处理媒体组消息
                download_tasks = []
                
                for msg in message:
                    if msg.media:
                        file_name = f'media_{msg.id}'
                        if hasattr(msg.media, 'document') and msg.media.document.mime_type:
                            ext = msg.media.document.mime_type.split('/')[-1]
                            file_name = f'{file_name}.{ext}'
                        temp_path = os.path.join(self.temp_dir, file_name)
                        
                        # 创建下载任务
                        download_tasks.append(self._download_file(msg, temp_path))
                
                # 并发执行所有下载任务，但限制并发数
                if download_tasks:
                    downloaded_files = await asyncio.gather(*download_tasks)
                    for downloaded_file in downloaded_files:
                        if downloaded_file:
                            media_files.append(downloaded_file)
                            
                caption = message[0].message if message[0].message else None
            else:
                # 处理单条消息
                if message.media:
                    temp_path = os.path.join(self.temp_dir, f'media_{message.id}')
                    downloaded_file = await self._download_file(message, temp_path)
                    if downloaded_file:
                        media_files.append(downloaded_file)
                    caption = message.message
                    
        except Exception as e:
            logger.error(f'下载媒体文件失败: {e}')
            # 清理已下载的文件
            for temp_file in media_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise
            
        return media_files, caption