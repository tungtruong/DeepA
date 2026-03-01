import asyncio
import os
import sqlite3
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from main import build_agent


load_dotenv()


def parse_allowed_user_ids(raw_value: str | None) -> set[int]:
    if not raw_value:
        return set()

    allowed_ids: set[int] = set()
    for item in raw_value.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        try:
            allowed_ids.add(int(cleaned))
        except ValueError as error:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_IDS không hợp lệ. Dùng danh sách số, ví dụ: 12345,67890"
            ) from error
    return allowed_ids


def normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        if text_parts:
            return "\n\n".join(part for part in text_parts if part)

    return str(content)


try:
    AGENT, MODEL_NAME = build_agent()
except ValueError as error:
    raise RuntimeError(str(error))


MAX_TURNS = 6
SAFE_CHUNK_SIZE = 3500
DB_PATH = os.getenv("CHAT_MEMORY_DB_PATH", "chat_memory.sqlite3")
ALLOWED_USER_IDS = parse_allowed_user_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS"))


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id_id ON chat_messages(chat_id, id)"
        )


def load_history(chat_id: int, max_messages: int) -> list[dict[str, str]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, max_messages),
        ).fetchall()

    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


def append_message(chat_id: int, role: str, content: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )


def trim_history(chat_id: int, max_messages: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM chat_messages
            WHERE chat_id = ?
              AND id NOT IN (
                  SELECT id
                  FROM chat_messages
                  WHERE chat_id = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            """,
            (chat_id, chat_id, max_messages),
        )


def clear_history(chat_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))


def split_message(text: str, max_chunk_size: int = SAFE_CHUNK_SIZE) -> list[str]:
    if len(text) <= max_chunk_size:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_chunk_size:
        split_at = remaining.rfind("\n", 0, max_chunk_size)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, max_chunk_size)
        if split_at == -1:
            split_at = max_chunk_size

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def reply_long_text(update: Update, text: str) -> None:
    if update.message is None:
        return

    async def send_chunk_safely(chunk: str) -> None:
        try:
            await update.message.reply_text(chunk)
        except BadRequest as error:
            if "message is too long" not in str(error).lower():
                raise

            if len(chunk) <= 200:
                raise

            for smaller_chunk in split_message(chunk, max_chunk_size=max(200, len(chunk) // 2)):
                await send_chunk_safely(smaller_chunk)

    for chunk in split_message(text):
        await send_chunk_safely(chunk)


async def ensure_user_allowed(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True

    if update.effective_user is None:
        return False

    if update.effective_user.id in ALLOWED_USER_IDS:
        return True

    if update.message is not None:
        await update.message.reply_text("Bạn không có quyền dùng bot này.")
    return False


def ask_agent(chat_id: int, prompt: str) -> str:
    max_messages = MAX_TURNS * 2
    history = load_history(chat_id, max_messages)
    history.append({"role": "user", "content": prompt})

    result = AGENT.invoke({"messages": history})
    answer = normalize_content(result["messages"][-1].content)

    append_message(chat_id, "user", prompt)
    append_message(chat_id, "assistant", answer)
    trim_history(chat_id, max_messages)

    return answer


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    if not await ensure_user_allowed(update):
        return
    clear_history(update.effective_chat.id)
    await update.message.reply_text(
        f"Bot đã sẵn sàng. Model: {MODEL_NAME}\nGửi tin nhắn để bắt đầu chat."
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    if not await ensure_user_allowed(update):
        return
    clear_history(update.effective_chat.id)
    await update.message.reply_text("Đã reset ngữ cảnh chat cho cuộc trò chuyện này.")


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    await update.message.reply_text(f"Telegram user ID của bạn: {update.effective_user.id}")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None or not update.message.text:
        return
    if not await ensure_user_allowed(update):
        return

    chat_id = update.effective_chat.id
    prompt = update.message.text.strip()
    if not prompt:
        await update.message.reply_text("Bạn chưa nhập nội dung.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        answer = await asyncio.to_thread(ask_agent, chat_id, prompt)
    except Exception as error:
        await update.message.reply_text(f"Lỗi khi gọi agent: {error}")
        return

    await reply_long_text(update, answer)


def main() -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong file .env")

    init_db()

    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    if ALLOWED_USER_IDS:
        print(
            f"Telegram bot đang chạy với model: {MODEL_NAME} | whitelist: {sorted(ALLOWED_USER_IDS)}"
        )
    else:
        print(f"Telegram bot đang chạy với model: {MODEL_NAME} | whitelist: OFF")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()