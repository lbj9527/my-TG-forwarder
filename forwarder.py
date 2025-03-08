import asyncio
from loguru import logger
from src.app import ForwarderApp

# 配置日志
logger.add("forwarder.log", rotation="10 MB", compression="zip", level="INFO")

async def main():
    """主函数"""
    app = ForwarderApp()
    try:
        await app.initialize()
        await app.run()
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
    finally:
        await app.close()

if __name__ == "__main__":
    asyncio.run(main())