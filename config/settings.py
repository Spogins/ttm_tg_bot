from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")

    # Claude (Anthropic)
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    claude_model: str = Field("claude-sonnet-4-6")

    # AssemblyAI
    assemblyai_api_key: str = Field(..., description="AssemblyAI API key for audio transcription")

    # MongoDB
    mongodb_uri: str = Field("mongodb://localhost:27017")
    mongodb_db_name: str = Field("ttm_bot")

    # Qdrant
    qdrant_host: str = Field("localhost")
    qdrant_port: int = Field(6333)
    qdrant_api_key: str = Field("")

    # Embeddings
    openai_api_key: str = Field(..., description="OpenAI API key for embeddings")
    embedding_model: str = Field("text-embedding-3-small")

    # Webhook
    webhook_url: str = Field(..., description="Public URL for Telegram webhook (e.g. https://yourdomain.com)")
    webhook_path: str = Field("/webhook")
    webapp_host: str = Field("0.0.0.0")
    webapp_port: int = Field(8080)

    # Token limits
    daily_token_limit: int = Field(30000)
    monthly_token_limit: int = Field(500000)


settings = Settings()
