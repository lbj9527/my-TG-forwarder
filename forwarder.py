import json
import asyncio
from telethon import TelegramClient
from telethon.tl.types import InputPeerChannel
from telethon.errors import FloodWaitError, ChannelPrivateError
from loguru import logger
import python_socks

# 配置日志
logger.add("forwarder.log", rotation="10 MB", compression="zip")

async def validate_config(config):
    """验证配置文件参数的有效性"""
    errors = []
    
    # 验证API凭证
    if 'api_id' not in config or not config['api_id']:
        errors.append("缺少api_id或api_id为空")
    else:
        # 确保api_id是字符串或整数
        if not isinstance(config['api_id'], (str, int)):
            errors.append("api_id必须是字符串或整数")
    
    if 'api_hash' not in config or not config['api_hash']:
        errors.append("缺少api_hash或api_hash为空")
    else:
        if not isinstance(config['api_hash'], str):
            errors.append("api_hash必须是字符串")
    
    # 验证代理设置
    if 'proxy' not in config:
        errors.append("缺少代理配置")
    else:
        proxy = config['proxy']
        if not isinstance(proxy, dict):
            errors.append("代理配置必须是一个对象")
        else:
            if 'enabled' not in proxy:
                errors.append("代理配置缺少enabled字段")
            elif not isinstance(proxy['enabled'], bool):
                errors.append("proxy.enabled必须是布尔值")
            
            if proxy['enabled']:
                # 只有当代理启用时才验证其他代理参数
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
    
    # 验证频道信息
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
    
    # 验证消息范围
    if 'message_range' not in config:
        errors.append("缺少message_range配置")
    else:
        message_range = config['message_range']
        if not isinstance(message_range, dict):
            errors.append("message_range必须是一个对象")
        else:
            if 'start_id' not in message_range:
                errors.append("message_range缺少start_id字段")
            elif not isinstance(message_range['start_id'], int) or message_range['start_id'] < 0:
                errors.append("start_id必须是非负整数")
            
            if 'end_id' not in message_range:
                errors.append("message_range缺少end_id字段")
            elif not isinstance(message_range['end_id'], int) or message_range['end_id'] < 0:
                errors.append("end_id必须是非负整数")
    
    # 验证会话名称
    if 'session_name' not in config or not config['session_name']:
        errors.append("缺少session_name或session_name为空")
    
    # 验证消息间隔时间
    if 'message_interval' not in config:
        errors.append("缺少message_interval配置")
    elif not isinstance(config['message_interval'], (int, float)) or config['message_interval'] < 0:
        errors.append("message_interval必须是非负数")
    
    # 如果有错误，抛出异常
    if errors:
        error_message = "\n".join(errors)
        logger.error(f"配置文件验证失败:\n{error_message}")
        raise ValueError(f"配置文件验证失败:\n{error_message}")
    
    return config

async def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 验证配置
            return await validate_config(config)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        raise

async def setup_client(config):
    # 设置代理
    proxy = None
    if config['proxy']['enabled']:
        proxy = {
            'proxy_type': python_socks.ProxyType.SOCKS5 if config['proxy']['type'].lower() == 'socks5' else python_socks.ProxyType.SOCKS4,
            'addr': config['proxy']['host'],
            'port': config['proxy']['port'],
            'username': config['proxy']['username'],
            'password': config['proxy']['password']
        }

    # 创建客户端
    if proxy:
        client = TelegramClient(
            config['session_name'],
            config['api_id'],
            config['api_hash'],
            proxy=proxy
        )
    else:
        client = TelegramClient(
            config['session_name'],
            config['api_id'],
            config['api_hash']
        )
    return client

def get_channel_identifier(channel):
    """获取频道的标识符，优先使用username，如果不存在则使用ID"""
    return getattr(channel, 'username', None) or f'private_{channel.id}'

async def forward_messages(client, config):
    try:
        # 获取源频道和目标频道
        source_channel = await client.get_entity(config['source_channel'])
        
        # 处理目标频道，支持单个频道或多个频道
        target_channels = []
        if isinstance(config['target_channel'], str):
            # 单个目标频道
            target_channel = await client.get_entity(config['target_channel'])
            target_channels.append(target_channel)
        elif isinstance(config['target_channel'], list):
            # 多个目标频道
            for channel in config['target_channel']:
                try:
                    # 检查channel是否为数字ID格式的字符串
                    if channel.startswith('-') and channel[1:].isdigit() or channel.isdigit():
                        # 将字符串形式的ID转换为整数
                        channel_id = int(channel)
                        # 使用InputPeerChannel构造输入实体
                        target_channel = await client.get_entity(channel_id)
                    else:
                        # 非数字ID格式，按原方式处理（用户名或链接）
                        target_channel = await client.get_entity(channel)
                    target_channels.append(target_channel)
                except Exception as e:
                    logger.error(f"无法获取目标频道 {channel}: {e}")
        
        if not target_channels:
            logger.error("没有有效的目标频道")
            return

        start_id = config['message_range']['start_id']
        end_id = config['message_range']['end_id']
        
        # 如果end_id为0，则获取源频道的最新消息ID
        if end_id == 0:
            # 获取最新消息（限制为1条）
            latest_messages = await client.get_messages(source_channel, limit=1)
            if latest_messages and len(latest_messages) > 0:
                end_id = latest_messages[0].id
                logger.info(f"检测到end_id为0，自动设置为最新消息ID: {end_id}")
            else:
                logger.error("无法获取最新消息ID")
                return
        
        logger.info(f"开始转发消息 从ID {start_id} 到 {end_id}")
        logger.info(f"目标频道数量: {len(target_channels)}")

        # 用于存储所有消息
        all_messages = []
        grouped_messages = {}

        # 第一次遍历：收集所有消息
        for message_id in range(start_id, end_id + 1):
            try:
                message = await client.get_messages(source_channel, ids=message_id)
                if not message:
                    logger.warning(f"消息ID {message_id} 不存在")
                    continue

                if message.grouped_id:
                    if message.grouped_id not in grouped_messages:
                        grouped_messages[message.grouped_id] = []
                    grouped_messages[message.grouped_id].append(message)
                else:
                    all_messages.append(message)

            except Exception as e:
                logger.error(f"处理消息失败 ID: {message_id}, 错误: {e}")
                continue

        # 处理媒体组消息，将排序后的媒体组添加到all_messages
        for grouped_id, messages in grouped_messages.items():
            messages.sort(key=lambda x: x.id)
            # 将整个媒体组作为一个元素添加到all_messages
            all_messages.append(messages)

        # 对所有消息按ID排序（对于媒体组，使用组内第一条消息的ID）
        all_messages.sort(key=lambda x: x[0].id if isinstance(x, list) else x.id)

        # 按顺序转发所有消息
        for message in all_messages:
            # 遍历所有目标频道
            for target_channel in target_channels:
                try:
                    if isinstance(message, list):
                        # 处理媒体组消息
                        grouped_id = message[0].grouped_id
                        # 收集所有媒体文件
                        media_files = [msg.media for msg in message]
                        # 使用第一条消息的文本作为整个组的标题
                        caption = message[0].message if message[0].message else None
                        # 一次性发送整个媒体组
                        if client is None:
                            logger.error(f"客户端对象为None，无法发送媒体组消息 Grouped ID: {grouped_id}")
                            continue
                        await client.send_file(
                            target_channel,
                            file=media_files,  # 传递媒体文件列表
                            caption=caption    # 使用第一条消息的文本作为标题
                        )
                        logger.info(f"成功发送媒体组消息 Grouped ID: {grouped_id} 到频道: {get_channel_identifier(target_channel)}")
                    else:
                        # 处理单条消息
                        media_type = "文本"
                        if message.media:
                            if hasattr(message.media, 'photo'):
                                media_type = "图片"
                            elif hasattr(message.media, 'document'):
                                media_type = "视频/文件"
                            
                            # 发送带媒体的消息，使用send_file保持媒体格式
                            await client.send_file(
                                target_channel,
                                file=message.media,
                                caption=message.message  # 文本内容作为caption
                            )
                        else:
                            # 发送纯文本消息，不显示来源
                            await client.send_message(
                                target_channel,
                                message=message.message  # 仅文本内容
                            )
                        logger.info(f"成功发送{media_type}消息 ID: {message.id} 到频道: {get_channel_identifier(target_channel)}")

                    # 每个目标频道发送后都等待指定的间隔时间
                    await asyncio.sleep(config['message_interval'])

                except FloodWaitError as e:
                    logger.warning(f"触发限制，等待 {e.seconds} 秒")
                    await asyncio.sleep(e.seconds)
                    # 重试发送
                    if isinstance(message, list):
                        # 处理媒体组消息
                        grouped_id = message[0].grouped_id
                        # 收集所有媒体文件
                        media_files = [msg.media for msg in message]
                        # 使用第一条消息的文本作为整个组的标题
                        caption = message[0].message if message[0].message else None
                        # 一次性发送整个媒体组
                        if client is None:
                            logger.error(f"客户端对象为None，无法发送媒体组消息 Grouped ID: {grouped_id}")
                            continue
                        await client.send_file(
                            target_channel,
                            file=media_files,  # 传递媒体文件列表
                            caption=caption    # 使用第一条消息的文本作为标题
                        )
                    else:
                        if message.media:
                            # 重试时也使用send_file保持媒体格式
                            await client.send_file(
                                target_channel,
                                file=message.media,
                                caption=message.message
                            )
                        else:
                            await client.send_message(
                                target_channel,
                                message=message.message
                            )
                except Exception as e:
                    error_id = message[0].id if isinstance(message, list) else message.id
                    logger.error(f"发送消息失败 ID: {error_id} 到频道: {get_channel_identifier(target_channel)}, 错误: {e}")
                    continue

    except ChannelPrivateError:
        logger.error("无法访问频道，请确保您有权限访问源频道和目标频道")
    except Exception as e:
        logger.error(f"转发过程中发生错误: {e}")

async def main():
    client = None
    try:
        # 加载配置
        config = await load_config()
        
        # 设置客户端
        client = await setup_client(config)
        
        # 启动客户端
        await client.connect()  # 使用connect()方法替代直接await start()
        
        if not await client.is_user_authorized():
            logger.info("请使用手机号码登录")
            await client.send_code_request(phone=input("请输入您的手机号码 (格式: +86xxxxxxxxxx): "))
            await client.sign_in(code=input("请输入收到的验证码: "))

        # 开始转发消息
        await forward_messages(client, config)
        
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
    finally:
        # 关闭客户端连接
        if client is not None and client.is_connected():
            await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())