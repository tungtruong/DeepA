# DeepAgents Starter (LangChain)

Project mẫu để bạn bắt đầu với `deepagents` của LangChain.

## 1) Tạo môi trường ảo và cài package

Trên Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Cấu hình API key

```powershell
Copy-Item .env.example .env
```

Sau đó mở file `.env` và điền ít nhất 1 model key (ví dụ `ANTHROPIC_API_KEY`).

Khuyên dùng OpenAI:

- Điền `OPENAI_API_KEY` trong `.env`
- Script sẽ tự chọn model mặc định `openai:gpt-4.1-mini`

Tuỳ chọn đổi model bằng biến:

```env
DEEPAGENT_MODEL=openai:gpt-5
```

`TAVILY_API_KEY` là optional, chỉ cần khi bạn muốn agent có khả năng tìm kiếm web.

## 3) Chạy agent

```powershell
python main.py
```

Nhập câu hỏi vào terminal, agent sẽ xử lý và in kết quả.

## 4) Cấu hình Telegram bot

Điền thêm biến này trong `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Bot sẽ lưu ngữ cảnh chat vào SQLite để restart vẫn nhớ hội thoại. Mặc định file DB là:

```env
CHAT_MEMORY_DB_PATH=chat_memory.sqlite3
```

Bạn có thể đổi sang path khác (ví dụ trên server):

```env
CHAT_MEMORY_DB_PATH=/opt/deepa/chat_memory.sqlite3
```

Whitelist (khuyến nghị):

```env
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

Nếu đặt biến này, chỉ các user ID trong danh sách mới dùng được bot.

## 5) Chạy Telegram bot

```powershell
python telegram_bot.py
```

Mở Telegram, tìm bot của bạn và nhắn `/start` để bắt đầu.

Lệnh hỗ trợ:

- `/reset`: xoá ngữ cảnh chat hiện tại.
- `/myid`: lấy Telegram user ID để điền vào `TELEGRAM_ALLOWED_USER_IDS`.

## 6) Copy từ Windows sang Arch

### Cách A: Dùng `scp` (nhanh nhất)

Chạy trên Windows PowerShell (đang đứng ở thư mục project):

```powershell
scp -r . user@<ARCH_IP>:/tmp/deepa
```

Sau đó SSH vào Arch:

```bash
ssh user@<ARCH_IP>
cd /tmp/deepa
```

### Cách B: Dùng Git

1. Push repo từ Windows lên GitHub/GitLab.
2. Trên Arch:

```bash
git clone <repo-url> /tmp/deepa
cd /tmp/deepa
```

## 7) Cài thành service trên Arch

Trong máy Arch, tại thư mục project:

```bash
chmod +x deploy/install_arch_service.sh
./deploy/install_arch_service.sh
```

Script sẽ:

- cài Python/pip,
- tạo user service `deepa-bot`,
- copy code vào `/opt/deepa`,
- tạo venv + cài dependencies,
- tạo env file `/etc/deepa/deepa.env`,
- tạo và bật `systemd` service.

Sau khi sửa key thật trong `/etc/deepa/deepa.env`:

```bash
sudo systemctl restart deepa-telegram-bot.service
sudo systemctl status deepa-telegram-bot.service
journalctl -u deepa-telegram-bot.service -f
```

## Ghi chú

- `deepagents` yêu cầu model hỗ trợ tool-calling.
- Nếu có cả OpenAI và Anthropic key, script sẽ ưu tiên OpenAI.