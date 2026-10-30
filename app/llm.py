import os

from dotenv import load_dotenv

load_dotenv()


def get_llm(provider=None, temperature=0):
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=temperature,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = os.getenv("ANTHROPIC_MODEL")
        if not model:
            raise ValueError("Set ANTHROPIC_MODEL in your .env file")
        return ChatAnthropic(
            model=model,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=temperature,
        )

    raise ValueError("Unknown LLM_PROVIDER: " + provider + " (use openai or anthropic)")
