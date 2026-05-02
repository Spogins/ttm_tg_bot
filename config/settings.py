# -*- coding: utf-8 -*-
"""
Application settings loaded from environment variables / .env file.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central config: Telegram, Anthropic, AssemblyAI, MongoDB, Qdrant, and token limits.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # telegram
    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")

    # claude (anthropic)
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    claude_model: str = Field("claude-sonnet-4-6")

    # assemblyai
    assemblyai_api_key: str = Field(..., description="AssemblyAI API key for audio transcription")

    # mongodb
    mongodb_uri: str = Field("mongodb://localhost:27017")
    mongodb_db_name: str = Field("ttm_bot")

    # qdrant
    qdrant_host: str = Field("localhost")
    qdrant_port: int = Field(6333)
    qdrant_api_key: str = Field("")

    # voyage ai embeddings
    voyage_api_key: str = Field(..., description="Voyage AI API key for embeddings")
    embedding_model: str = Field("voyage-code-3")

    # webhook (ignored in dev_mode)
    webhook_url: str = Field(..., description="Public URL for Telegram webhook (e.g. https://yourdomain.com)")
    webhook_path: str = Field("/webhook")
    webapp_host: str = Field("0.0.0.0")
    webapp_port: int = Field(8080)

    # dev mode: use polling instead of webhook
    dev_mode: bool = Field(False)

    # per-user token limits for LLM requests
    daily_token_limit: int = Field(30000)
    monthly_token_limit: int = Field(500000)


settings = Settings()
