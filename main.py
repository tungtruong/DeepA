import os
import sys
from typing import Literal

from deepagents import create_deep_agent
from dotenv import load_dotenv


load_dotenv()


def configure_console_encoding() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"Trời ở {city} luôn nắng đẹp!"


tools = [get_weather]

tavily_api_key = os.getenv("TAVILY_API_KEY")
if tavily_api_key:
    from tavily import TavilyClient

    tavily_client = TavilyClient(api_key=tavily_api_key)

    def internet_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False,
    ):
        """Run a web search."""
        return tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )

    tools.append(internet_search)


system_prompt = """Bạn là một deep agent hữu ích.

- Luôn lập kế hoạch ngắn trước khi làm các tác vụ phức tạp.
- Ưu tiên trả lời rõ ràng, có cấu trúc.
- Nếu có tool tìm kiếm internet, hãy dùng khi cần thông tin mới.
"""


def resolve_model() -> str:
    explicit_model = os.getenv("DEEPAGENT_MODEL")
    if explicit_model:
        return explicit_model

    if os.getenv("OPENAI_API_KEY"):
        return "openai:gpt-4.1-mini"

    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude-sonnet-4-5-20250929"

    raise ValueError(
        "Thiếu API key. Hãy đặt OPENAI_API_KEY (khuyên dùng) hoặc ANTHROPIC_API_KEY trong file .env"
    )


def build_agent():
    model_name = resolve_model()
    built_agent = create_deep_agent(
        model=model_name,
        tools=tools,
        system_prompt=system_prompt,
    )
    return built_agent, model_name


def main() -> None:
    try:
        agent, model_name = build_agent()
    except ValueError as error:
        print(str(error))
        return

    print(f"Đang dùng model: {model_name}")

    question = input("Nhập yêu cầu cho agent: ").strip()
    if not question:
        print("Bạn chưa nhập yêu cầu.")
        return

    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    last_message = result["messages"][-1]

    if isinstance(last_message.content, str):
        print("\n=== Kết quả ===")
        print(last_message.content)
    else:
        print("\n=== Kết quả ===")
        print(str(last_message.content))


if __name__ == "__main__":
    main()