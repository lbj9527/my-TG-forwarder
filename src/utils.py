from typing import Optional, Tuple
import re
from loguru import logger

def parse_channel_link(channel_link: str) -> Optional[str]:
    """
    解析Telegram频道链接，支持私有频道链接格式
    
    私有频道链接格式: https://t.me/c/频道ID/消息ID
    公开频道链接格式: https://t.me/频道名称
    
    Args:
        channel_link: Telegram频道链接
        
    Returns:
        解析后的频道标识符，私有频道返回数字ID，公开频道返回用户名
    """
    try:
        # 匹配私有频道链接格式: https://t.me/c/频道ID/消息ID
        private_channel_pattern = r'https?://t\.me/c/([0-9]+)(?:/[0-9]+)?'
        private_match = re.match(private_channel_pattern, channel_link)
        
        if private_match:
            # 提取私有频道ID
            channel_id = private_match.group(1)
            logger.info(f"解析到私有频道ID: {channel_id}")
            # 检查ID是否已经包含-100前缀
            if not channel_id.startswith("-100"):
                # 为私有频道ID添加-100前缀
                channel_id = f"-100{channel_id}"
                logger.info(f"添加前缀后的私有频道ID: {channel_id}")
            else:
                logger.info(f"ID已包含前缀: {channel_id}")
            return channel_id
        
        # 匹配公开频道链接格式: https://t.me/频道名称
        public_channel_pattern = r'https?://t\.me/([\w_]+)(?:/[0-9]+)?'
        public_match = re.match(public_channel_pattern, channel_link)
        
        if public_match:
            # 提取公开频道用户名
            username = public_match.group(1)
            logger.info(f"解析到公开频道用户名: {username}")
            return username
        
        # 如果不是链接格式，直接返回原始值（可能是频道ID或用户名）
        logger.info(f"未识别为链接格式，使用原始值: {channel_link}")
        return channel_link
        
    except Exception as e:
        logger.error(f"解析频道链接失败: {e}")
        return None