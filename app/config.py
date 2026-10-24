import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    tinyfish_api_key: str
    anthropic_api_key: str
    hf_token: str
    llm_provider: str
    llm_model: str
    agent_model: str
    max_steps: int
    max_agent_runs: int
    db_path: str
    scheduler_tick: float
    tool_result_char_limit: int = 6000


def get_settings() -> Settings:
    return Settings(
        tinyfish_api_key=os.getenv("TINYFISH_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        hf_token=os.getenv("HF_TOKEN", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "huggingface"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        agent_model=os.getenv("AGENT_MODEL", "claude-sonnet-5-5"),
        max_steps=int(os.getenv("MAX_STEPS", "12")),
        max_agent_runs=int(os.getenv("MAX_AGENT_RUNS", "4")),
        db_path=os.getenv("DB_PATH", "autopilot.db"),
        scheduler_tick=float(os.getenv("SCHEDULER_TICK", "10")),
    )
