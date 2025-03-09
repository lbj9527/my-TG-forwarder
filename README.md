Telegram 消息转发工具使用说明

1. 安装步骤

   - 确保已安装 Python 3.7 或更高版本
   - 安装依赖包：pip install -r requirements.txt

2. 配置文件说明（config.json）

   2.1 API 凭证

   - api_id：在 https://my.telegram.org/apps 获取的 API ID
   - api_hash：在 https://my.telegram.org/apps 获取的 API Hash

     2.2 代理设置

   - enabled：是否启用代理（true/false）
   - type：代理类型（支持 socks5 或 socks4）
   - host：代理服务器地址
   - port：代理服务器端口
   - username：代理用户名（可选）
   - password：代理密码（可选）

     2.3 频道配置

   - source_channel：源频道，支持以下格式：

     - 公有频道/群组链接：https://t.me/channel_name
     - 用户名：@channel_name
     - 私有频道/群组链接：直接复制消息链接https://t.me/c/2316009417/43405

   - target_channel：目标频道，支持单个频道或频道数组，格式如下：

     - 公有频道链接：https://t.me/channel_name
     - 用户名：@channel_name
     - 私有频道链接：直接复制消息链接https://t.me/c/2316009417/43405

       2.4 消息范围设置

   - message_range：

     - start_id：起始消息 ID
     - end_id：结束消息 ID（设为 0 表示转发到最新消息）

       2.5 其他设置

   - message_interval：消息转发间隔时间（秒），建议设置大于 0 的值以避免触发限制
   - session_name：会话名称，用于保存登录状态
   - hide_author：是否隐藏转发消息的原作者（true/false），默认为 true 表示隐藏原作者信息

3. 运行程序

   - 运行命令：python forwarder.py
   - 首次运行需要使用手机号登录并输入验证码
   - 登录成功后会自动保存会话，下次运行无需重新登录

4. 注意事项

   - 请确保有权限访问源频道和目标频道
   - 建议适当设置消息转发间隔，避免触发 Telegram 的限制
   - 如遇到错误，请查看 forwarder.log 日志文件

5. 单元测试

   5.1 测试环境准备

   - 安装测试依赖：pip install pytest pytest-asyncio pytest-mock
   - 确保在项目根目录下运行测试

     5.2 测试用例说明

   - test_config.py：测试配置文件加载和验证
   - test_client.py：测试客户端连接和授权
   - test_message.py：测试消息收集和转发

     5.3 运行测试

   - 运行所有测试：pytest tests/
   - 运行指定模块：pytest tests/test_config.py
   - 查看详细输出：pytest -v tests/
   - 显示测试覆盖率：pytest --cov=src tests/

6. 常见问题
   Q：如何获取频道 ID？
   A：可以通过转发频道消息到 @getidsbot 获取

   Q：为什么会出现 FloodWaitError 错误？
   A：这是 Telegram 的限制机制，请增加 message_interval 的值

   Q：如何处理代理连接问题？
   A：确保代理服务器正常运行，并正确配置代理参数
