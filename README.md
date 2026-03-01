# OpenCode Telegram Bot

通过 Telegram 对接 OpenCode Server 的机器人

## 功能特性

- 💬 与 OpenCode AI 自然对话
- 🆕 创建和管理多个会话
- 📁 代码分析和文件操作
- 🔄 撤销/重做操作支持
- ⚡ 异步处理，响应迅速

## 快速开始

### 1. 安装依赖

```bash
cd ~/opencode-telegram-bot
pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# Telegram Bot Token (从 @BotFather 获取)
TELEGRAM_BOT_TOKEN=你的机器人Token

# OpenCode Server 配置
OPENCODE_SERVER_URL=http://127.0.0.1:4096

# 如果启用了认证，取消下面注释并填写
# OPENCODE_USERNAME=opencode
# OPENCODE_PASSWORD=你的密码
```

### 3. 启动 Bot

确保 OpenCode Server 已在运行：

```bash
# 在另一个终端运行
opencode serve --port 4096
```

然后启动 Telegram Bot：

```bash
python bot.py
```

## 使用指南

### 基础命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始对话 |
| `/new` | 创建新的 OpenCode 会话 |
| `/sessions` | 查看会话列表 |
| `/switch <id>` | 切换到指定会话 |
| `/delete` | 删除当前会话 |
| `/status` | 检查 OpenCode Server 状态 |
| `/init` | 初始化项目（创建 AGENTS.md） |
| `/undo` | 撤销上一步操作 |
| `/help` | 显示帮助信息 |

### 示例对话

创建会话后，直接发送消息即可：

```
用户: 帮我分析这个项目的代码结构

OpenCode: 我来分析一下项目结构...
```

```
用户: 如何优化 src/main.py 中的这个函数？

OpenCode: 建议如下优化...
```

```
用户: /init

OpenCode: 正在初始化项目...
```

## 项目结构

```
opencode-telegram-bot/
├── bot.py              # 主程序
├── opencode_client.py  # OpenCode Server 客户端
├── requirements.txt    # 依赖列表
├── .env.example       # 环境变量示例
└── README.md          # 本文档
```

## 常见问题

### Q: 无法连接到 OpenCode Server？

确保 OpenCode Server 正在运行：

```bash
opencode serve --port 4096
```

检查地址是否正确（默认是 `http://127.0.0.1:4096`）

### Q: Telegram Bot 不响应？

1. 检查 Token 是否正确
2. 确保 Bot 没有被其他程序占用
3. 查看日志输出排查错误

### Q: 消息太长被截断？

Telegram 单条消息限制约 4000 字符。长回复会被自动截断，可以在 `.env` 中调整 `MAX_MESSAGE_LENGTH`。

## 安全提示

⚠️ **重要**：
- 不要分享你的 `TELEGRAM_BOT_TOKEN`
- 如果 Token 泄露，立即在 [@BotFather](https://t.me/BotFather) 中执行 `/revoke` 重新生成
- 如果启用了 OpenCode Server 认证，请使用强密码

## 技术栈

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [aiohttp](https://docs.aiohttp.org/) - 异步 HTTP 客户端
- [OpenCode Server](https://opencode.ai/docs/server/) - OpenCode HTTP API

## 许可证

MIT