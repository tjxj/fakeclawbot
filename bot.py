"""
OpenCode Telegram Bot
通过 Telegram 对接 OpenCode Server
"""

import os
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from opencode_client import OpenCodeClient

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENCODE_SERVER_URL = os.getenv("OPENCODE_SERVER_URL", "http://127.0.0.1:4096")
OPENCODE_USERNAME = os.getenv("OPENCODE_USERNAME")
OPENCODE_PASSWORD = os.getenv("OPENCODE_PASSWORD")
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))

# Telegram Markdown 格式系统指令
# 注入到每条用户消息前，确保 OpenCode 返回的内容符合 Telegram 解析要求
TELEGRAM_FORMAT_INSTRUCTION = (
    "[格式要求] 你的回复将通过 Telegram 发送，请严格遵守以下格式规则：\n"
    "1. 加粗使用单星号 *粗体* (不要用**)\n"
    "2. 斜体使用下划线 _斜体_\n"
    "3. 行内代码用单反引号 `code`，代码块用三反引号\n"
    "4. 链接用 [文本](URL) 格式\n"
    "5. 不要使用 # 号标题，不要使用 HTML 标签\n"
    "6. 特殊字符（如 _、*、`、[）在非格式化场景下需避免歧义\n"
    "7. 保持简洁排版，避免复杂的嵌套格式\n\n"
    "[用户消息] "
)


# 用户会话管理
class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.opencode_session_id: Optional[str] = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_count = 0
        self.selected_model: Optional[str] = None

    def update_activity(self):
        self.last_activity = datetime.now()
        self.message_count += 1


# 全局用户会话存储
user_sessions: Dict[int, UserSession] = {}


async def get_or_create_user_session(user_id: int) -> UserSession:
    """获取或创建用户会话"""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
        logger.info(f"为 user_id={user_id} 创建了新会话")
    return user_sessions[user_id]


async def get_opencode_client() -> OpenCodeClient:
    """创建 OpenCode 客户端"""
    return OpenCodeClient(
        base_url=OPENCODE_SERVER_URL,
        username=OPENCODE_USERNAME,
        password=OPENCODE_PASSWORD,
    )


# ============ 命令处理 ============


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    user = update.effective_user
    welcome_text = f"""
👋 你好 {user.first_name}!

我是 OpenCode Telegram Bot，可以帮助你通过 Telegram 使用 OpenCode AI。

📋 可用命令：
/new - 创建新的 OpenCode 会话
/sessions - 查看当前会话列表
/status - 查看服务器状态
/help - 显示帮助信息

💬 使用方法：
1. 先使用 /new 创建会话
2. 直接发送消息与 OpenCode 对话
3. 支持自然语言提问、代码分析等功能

⚡ OpenCode Server: {OPENCODE_SERVER_URL}
    """
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_text = f"""
📖 OpenCode Telegram Bot 使用指南

🚀 基础命令：
/start - 开始对话
/new - 创建新的 OpenCode 会话
/sessions - 查看会话列表
/switch <id> - 切换到指定会话
/delete - 删除当前会话
/status - 检查服务器状态
/model <name> - 切换模型 (如: /model qwen:7b)
/help - 显示此帮助

💻 代码操作：
直接发送消息即可与 OpenCode 对话

📝 示例问题：
• "帮我分析这个项目的代码结构"
• "如何优化这个函数的性能？"
• "解释一下 @src/main.py 的作用"
• "/init 初始化项目"

⚙️ OpenCode Server: {OPENCODE_SERVER_URL}
    """
    await update.message.reply_text(help_text)


async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建新会话"""
    user_id = update.effective_user.id

    # 询问会话标题（可选）
    await update.message.reply_text(
        "🆕 创建新的 OpenCode 会话...\n"
        "请输入会话标题（直接回复 /cancel 取消，或回复 /skip 跳过）："
    )
    return "WAITING_FOR_TITLE"


async def receive_session_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收会话标题"""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "/cancel":
        await update.message.reply_text("❌ 已取消创建会话")
        return ConversationHandler.END

    title = None if text == "/skip" else text

    try:
        async with await get_opencode_client() as client:
            session = await client.create_session(title=title)
            session_id = session.get("id")

            # 保存用户会话
            user_session = await get_or_create_user_session(user_id)
            user_session.opencode_session_id = session_id
            user_session.update_activity()

            display_title = title or "未命名会话"
            await update.message.reply_text(
                f"✅ 会话创建成功！\n"
                f"📝 标题: {display_title}\n"
                f"🆔 ID: {session_id}\n\n"
                f"现在可以直接发送消息与 OpenCode 对话了！"
            )
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        await update.message.reply_text(f"❌ 创建会话失败: {str(e)}")

    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消当前操作"""
    await update.message.reply_text("❌ 操作已取消")
    return ConversationHandler.END


async def list_sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出所有会话"""
    user_id = update.effective_user.id

    try:
        async with await get_opencode_client() as client:
            sessions = await client.list_sessions()

            if not sessions:
                await update.message.reply_text(
                    "📭 当前没有任何会话\n使用 /new 创建新会话"
                )
                return

            user_session = await get_or_create_user_session(user_id)
            current_id = user_session.opencode_session_id

            text = "📋 会话列表:\n\n"
            for idx, session in enumerate(sessions[:10], 1):  # 最多显示10个
                session_id = session.get("id", "unknown")[:8] + "..."
                title = session.get("title") or "未命名"
                current_marker = " ⭐" if session.get("id") == current_id else ""
                text += f"{idx}. {title}{current_marker}\n   ID: {session_id}\n\n"

            if len(sessions) > 10:
                text += f"... 还有 {len(sessions) - 10} 个会话\n"

            text += "\n💡 使用 /switch <id> 切换会话"
            await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        await update.message.reply_text(f"❌ 获取会话列表失败: {str(e)}")


async def switch_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换会话"""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "🔄 请提供会话 ID\n例如: /switch abc123\n\n使用 /sessions 查看可用会话"
        )
        return

    session_id = context.args[0]

    try:
        async with await get_opencode_client() as client:
            # 验证会话存在
            session = await client.get_session(session_id)

            # 更新用户会话
            user_session = await get_or_create_user_session(user_id)
            user_session.opencode_session_id = session_id
            user_session.update_activity()

            title = session.get("title") or "未命名"
            await update.message.reply_text(
                f"✅ 已切换到会话: {title}\n🆔 ID: {session_id}"
            )

    except Exception as e:
        logger.error(f"切换会话失败: {e}")
        await update.message.reply_text(f"❌ 切换会话失败: {str(e)}")


async def delete_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除当前会话"""
    user_id = update.effective_user.id
    user_session = await get_or_create_user_session(user_id)

    if not user_session.opencode_session_id:
        await update.message.reply_text("❌ 当前没有活跃的会话")
        return

    try:
        async with await get_opencode_client() as client:
            session_id = user_session.opencode_session_id
            await client.delete_session(session_id)
            user_session.opencode_session_id = None

            await update.message.reply_text("✅ 会话已删除")

    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        await update.message.reply_text(f"❌ 删除会话失败: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """检查服务器状态"""
    try:
        async with await get_opencode_client() as client:
            health = await client.health_check()

            text = f"""
✅ OpenCode Server 运行正常

🌐 地址: {OPENCODE_SERVER_URL}
📦 版本: {health.get("version", "unknown")}
❤️ 状态: 健康

💡 使用 /new 开始新的对话
            """
            await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"检查服务器状态失败: {e}")
        await update.message.reply_text(
            f"❌ 无法连接到 OpenCode Server\n"
            f"地址: {OPENCODE_SERVER_URL}\n"
            f"错误: {str(e)}\n\n"
            f"请确保 OpenCode Server 已启动: opencode serve"
        )


async def init_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """初始化项目（执行 /init）"""
    user_id = update.effective_user.id
    user_session = await get_or_create_user_session(user_id)

    if not user_session.opencode_session_id:
        await update.message.reply_text("❌ 请先使用 /new 创建会话")
        return

    # 发送正在处理的提示
    processing_msg = await update.message.reply_text("🔄 正在初始化项目，请稍候...")

    try:
        async with await get_opencode_client() as client:
            # 使用默认模型 siliconflow/Pro/moonshotai/Kimi-K2.5
            model = user_session.selected_model or "siliconflow/Pro/moonshotai/Kimi-K2.5"
            result = await client.execute_command(
                session_id=user_session.opencode_session_id, command="init", model=model
            )

            # 提取回复内容
            parts = result.get("parts", [])
            info = result.get("info", {})
            error = info.get("error")

            response_text = ""
            for part in parts:
                if part.get("type") == "text":
                    response_text += part.get("content") or part.get("text") or ""

            if not response_text.strip() and error:
                error_msg = (
                    error.get("data", {}).get("message")
                    or error.get("message")
                    or str(error)
                )
                response_text = f"❌ OpenCode Server 错误:\n{error_msg}"

            # 截断过长的消息
            if len(response_text) > MAX_MESSAGE_LENGTH:
                response_text = (
                    response_text[: MAX_MESSAGE_LENGTH - 100] + "\n\n...(消息已截断)"
                )

            try:
                await processing_msg.edit_text(
                    f"✅ 项目初始化完成！\n\n{response_text or '已创建 AGENTS.md'}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning(f"Telegram Markdown 解析失败，已回退为纯文本: {e}")
                await processing_msg.edit_text(
                    f"✅ 项目初始化完成！\n\n{response_text or '已创建 AGENTS.md'}"
                )
            user_session.update_activity()

    except Exception as e:
        logger.error(f"初始化项目失败: {e}")
        await processing_msg.edit_text(f"❌ 初始化失败: {str(e)}")


# 预定义的可用模型列表
AVAILABLE_MODELS = {
    # Quotio 模型 - Claude 系列
    "claude-opus-4-6-thinking": "quotio/claude-opus-4-6-thinking",
    "claude-sonnet-4-6": "quotio/claude-sonnet-4-6",
    # Quotio 模型 - Gemini 系列
    "gemini-2.5-flash": "quotio/gemini-2.5-flash",
    "gemini-2.5-flash-lite": "quotio/gemini-2.5-flash-lite",
    "gemini-2.5-pro": "quotio/gemini-2.5-pro",
    "gemini-3-flash-preview": "quotio/gemini-3-flash-preview",
    "gemini-3-pro-preview": "quotio/gemini-3-pro-preview",
    "gemini-3.1-flash-image": "quotio/gemini-3.1-flash-image",
    "gemini-3.1-pro-high": "quotio/gemini-3.1-pro-high",
    "gemini-3.1-pro-low": "quotio/gemini-3.1-pro-low",
    # Quotio 模型 - GPT 系列
    "gpt-oss-120b-medium": "quotio/gpt-oss-120b-medium",
    # Quotio 模型 - Tab 系列
    "tab_flash_lite_preview": "quotio/tab_flash_lite_preview",
    "tab_jump_flash_lite_preview": "quotio/tab_jump_flash_lite_preview",
    # Ollama 模型
    "glm-5": "ollama/glm-5:cloud",
    "kimi-k2.5": "ollama/kimi-k2.5:cloud",
    "minimax-m2.5": "ollama/minimax-m2.5:cloud",
    # Zen 免费模型 (provider = opencode)
    "minimax-m2.5-free": "opencode/minimax-m2.5-free",
    "minimax-m2.1-free": "opencode/minimax-m2.1-free",
    "kimi-k2.5-free": "opencode/kimi-k2.5-free",
    "glm-5-free": "opencode/glm-5-free",
    "big-pickle": "opencode/big-pickle",
    "trinity-large-preview-free": "opencode/trinity-large-preview-free",
    # SiliconFlow 模型
    "siliconflow-m2.5": "siliconflow/Pro/MiniMaxAI/MiniMax-M2.5",
    "siliconflow-glm5": "siliconflow/Pro/zai-org/GLM-5",
    "siliconflow-kimi2.5": "siliconflow/Pro/moonshotai/Kimi-K2.5",
}


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置使用的模型"""
    user_id = update.effective_user.id
    user_session = await get_or_create_user_session(user_id)

    if not context.args:
        # 显示当前模型和可用模型列表
        current_model = (
            user_session.selected_model or "siliconflow/Pro/moonshotai/Kimi-K2.5 (默认)"
        )

        models_text = "🤖 可用模型列表:\n\n"
        models_text += "【Claude 系列 - quotio】\n"
        models_text += "  1. claude-opus-4-6-thinking\n"
        models_text += "  2. claude-sonnet-4-6\n\n"
        models_text += "【Gemini 系列 - quotio】\n"
        models_text += "  3. gemini-2.5-flash\n"
        models_text += "  4. gemini-2.5-flash-lite\n"
        models_text += "  5. gemini-2.5-pro\n"
        models_text += "  6. gemini-3-flash-preview\n"
        models_text += "  7. gemini-3-pro-preview\n"
        models_text += "  8. gemini-3.1-flash-image\n"
        models_text += "  9. gemini-3.1-pro-high\n"
        models_text += "  10. gemini-3.1-pro-low\n\n"
        models_text += "【GPT 系列 - quotio】\n"
        models_text += "  11. gpt-oss-120b-medium\n\n"
        models_text += "【Tab 系列 - quotio】\n"
        models_text += "  12. tab_flash_lite_preview\n"
        models_text += "  13. tab_jump_flash_lite_preview\n\n"
        models_text += "【Ollama 模型】\n"
        models_text += "  14. glm-5\n"
        models_text += "  15. kimi-k2.5\n"
        models_text += "  16. minimax-m2.5\n\n"
        models_text += "【Zen 免费模型 ✨】\n"
        models_text += "  17. minimax-m2.5-free\n"
        models_text += "  18. minimax-m2.1-free\n"
        models_text += "  19. kimi-k2.5-free\n"
        models_text += "  20. glm-5-free\n"
        models_text += "  21. big-pickle\n"
        models_text += "  22. trinity-large-preview-free\n\n"
        models_text += "【SiliconFlow 模型⚡】\n"
        models_text += "  23. siliconflow-m2.5\n"
        models_text += "  24. siliconflow-glm5\n"
        models_text += "  25. siliconflow-kimi2.5\n\n"
        models_text += f"📌 当前模型: {current_model}\n\n"
        models_text += "💡 使用方法:\n"
        models_text += "  • /model gemini-3.1-pro-high\n"
        models_text += "  • /model 1 (使用数字快速选择)\n"
        models_text += "  • /model clear (恢复默认)"

        await update.message.reply_text(models_text)
        return

    model_arg = context.args[0].lower()

    if model_arg == "clear":
        user_session.selected_model = None
        await update.message.reply_text(
            "✅ 已恢复默认模型 (siliconflow/Pro/moonshotai/Kimi-K2.5)"
        )
        return

    # 检查是否是数字选择
    if model_arg.isdigit():
        model_map = {
            "1": "claude-opus-4-6-thinking",
            "2": "claude-sonnet-4-6",
            "3": "gemini-2.5-flash",
            "4": "gemini-2.5-flash-lite",
            "5": "gemini-2.5-pro",
            "6": "gemini-3-flash-preview",
            "7": "gemini-3-pro-preview",
            "8": "gemini-3.1-flash-image",
            "9": "gemini-3.1-pro-high",
            "10": "gemini-3.1-pro-low",
            "11": "gpt-oss-120b-medium",
            "12": "tab_flash_lite_preview",
            "13": "tab_jump_flash_lite_preview",
            "14": "glm-5",
            "15": "kimi-k2.5",
            "16": "minimax-m2.5",
            "17": "minimax-m2.5-free",
            "18": "minimax-m2.1-free",
            "19": "kimi-k2.5-free",
            "20": "glm-5-free",
            "21": "big-pickle",
            "22": "trinity-large-preview-free",
            "23": "siliconflow-m2.5",
            "24": "siliconflow-glm5",
            "25": "siliconflow-kimi2.5",
        }
        if model_arg in model_map:
            model_arg = model_map[model_arg]
        else:
            await update.message.reply_text(
                f"❌ 无效的选择: {model_arg}\n请使用 1-25 之间的数字"
            )
            return

    # 查找模型完整名称
    if model_arg in AVAILABLE_MODELS:
        full_model_name = AVAILABLE_MODELS[model_arg]
        user_session.selected_model = full_model_name
        await update.message.reply_text(
            f"✅ 已切换到模型: {model_arg}\n完整名称: {full_model_name}"
        )
    else:
        # 用户直接输入了完整的模型名称
        user_session.selected_model = context.args[0]
        await update.message.reply_text(f"✅ 已切换到模型: {context.args[0]}")


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """撤销上一步操作"""
    user_id = update.effective_user.id
    user_session = await get_or_create_user_session(user_id)

    if not user_session.opencode_session_id:
        await update.message.reply_text("❌ 请先使用 /new 创建会话")
        return

    try:
        async with await get_opencode_client() as client:
            # 获取最后一条消息
            messages = await client.list_messages(
                session_id=user_session.opencode_session_id, limit=5
            )

            if not messages:
                await update.message.reply_text("❌ 没有找到可撤销的消息")
                return

            # 找到最后一条助手消息
            for msg in reversed(messages):
                if msg.get("info", {}).get("role") == "assistant":
                    message_id = msg.get("info", {}).get("id")
                    await client.revert_message(
                        session_id=user_session.opencode_session_id,
                        message_id=message_id,
                    )
                    await update.message.reply_text("✅ 已撤销上一步操作")
                    return

            await update.message.reply_text("❌ 没有找到可撤销的助手回复")

    except Exception as e:
        logger.error(f"撤销操作失败: {e}")
        await update.message.reply_text(f"❌ 撤销失败: {str(e)}")


# ============ 消息处理 ============


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理普通消息"""
    user_id = update.effective_user.id
    text = update.message.text

    user_session = await get_or_create_user_session(user_id)

    # 检查是否有活跃会话
    if not user_session.opencode_session_id:
        await update.message.reply_text(
            "⚠️ 还没有创建会话\n\n请使用 /new 创建新的 OpenCode 会话"
        )
        return

    # 发送正在输入的提示
    processing_msg = await update.message.reply_text("🤔 正在思考中...")

    try:
        async with await get_opencode_client() as client:
            # 使用默认模型 siliconflow/Pro/moonshotai/Kimi-K2.5
            model = user_session.selected_model or "siliconflow/Pro/moonshotai/Kimi-K2.5"
            result = await client.send_message(
                session_id=user_session.opencode_session_id,
                content=TELEGRAM_FORMAT_INSTRUCTION + text,
                model=model,
            )

            # 提取回复内容
            parts = result.get("parts", [])
            logger.info(f"OpenCode Result: {result}")
            info = result.get("info", {})
            error = info.get("error")

            response_text = ""
            for part in parts:
                if part.get("type") == "text":
                    response_text += part.get("content") or part.get("text") or ""

            if not response_text.strip() and error:
                error_msg = (
                    error.get("data", {}).get("message")
                    or error.get("message")
                    or str(error)
                )
                response_text = f"❌ OpenCode Server 错误:\n{error_msg}"

            # 截断过长的消息
            if len(response_text) > MAX_MESSAGE_LENGTH:
                response_text = (
                    response_text[: MAX_MESSAGE_LENGTH - 100]
                    + "\n\n...(消息过长，已截断)"
                )

            # 如果消息为空，显示提示
            if not response_text.strip():
                response_text = "（OpenCode 返回了空回复）"

            try:
                await processing_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.warning(f"Telegram Markdown 解析失败，已回退为纯文本: {e}")
                await processing_msg.edit_text(response_text)
            user_session.update_activity()

    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        await processing_msg.edit_text(f"❌ 处理消息时出错: {str(e)}")


# ============ 主程序 ============


def main():
    """启动 Bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("错误: 未设置 TELEGRAM_BOT_TOKEN 环境变量")
        print("请在 .env 文件中设置 TELEGRAM_BOT_TOKEN")
        return

    # 创建 Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 添加对话处理器（用于创建会话时输入标题）
    new_session_conv = ConversationHandler(
        entry_points=[CommandHandler("new", new_session_command)],
        states={
            "WAITING_FOR_TITLE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_session_title)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    # 添加命令处理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(new_session_conv)
    application.add_handler(CommandHandler("sessions", list_sessions_command))
    application.add_handler(CommandHandler("switch", switch_session_command))
    application.add_handler(CommandHandler("delete", delete_session_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("init", init_command))
    application.add_handler(CommandHandler("undo", undo_command))
    application.add_handler(CommandHandler("model", model_command))

    # 添加消息处理器
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # 启动 Bot
    logger.info(f"Starting OpenCode Telegram Bot...")
    logger.info(f"OpenCode Server: {OPENCODE_SERVER_URL}")

    print(f"🤖 Bot 已启动！")
    print(f"🔗 OpenCode Server: {OPENCODE_SERVER_URL}")
    print(f"💡 在 Telegram 中发送 /start 开始使用")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()