import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM Server
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen2.5-3B")

    # Twitter credentials
    TWITTER_USERNAME: str = os.getenv("TWITTER_USERNAME", "")
    TWITTER_PASSWORD: str = os.getenv("TWITTER_PASSWORD", "")
    TWITTER_EMAIL: str = os.getenv("TWITTER_EMAIL", "")

    # Browser settings
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    BROWSER_WS_ENDPOINT: str = os.getenv("BROWSER_WS_ENDPOINT", "")
    BROWSER_USER_DATA_DIR: str = os.getenv("BROWSER_USER_DATA_DIR", "")
    BROWSER_EXECUTABLE_PATH: str = os.getenv("BROWSER_EXECUTABLE_PATH", "")

    # Behavior
    MIN_DELAY_SECONDS: int = int(os.getenv("MIN_DELAY_SECONDS", "8"))
    MAX_DELAY_SECONDS: int = int(os.getenv("MAX_DELAY_SECONDS", "18"))
    ACTIVE_HOURS_START: int = int(os.getenv("ACTIVE_HOURS_START", "8"))
    ACTIVE_HOURS_END: int = int(os.getenv("ACTIVE_HOURS_END", "22"))
    MAX_TWEETS_PER_SESSION: int = int(os.getenv("MAX_TWEETS_PER_SESSION", "8"))
    MAX_LIKES_PER_SESSION: int = int(os.getenv("MAX_LIKES_PER_SESSION", "20"))
    MAX_REPLIES_PER_SESSION: int = int(os.getenv("MAX_REPLIES_PER_SESSION", "10"))
    MAX_RETWEETS_PER_SESSION: int = int(os.getenv("MAX_RETWEETS_PER_SESSION", "8"))
    MAX_ENGAGEMENTS: int = int(os.getenv("MAX_ENGAGEMENTS", "30"))

    # Persona
    DEFAULT_PERSONA: str = os.getenv("DEFAULT_PERSONA", "finance_investor")


config = Config()
