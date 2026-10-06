"""Application configuration loaded from environment variables."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Travel Planner Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM configuration (Google Gemini)
    google_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model identifier")

    # Places / Hotel APIs (Optional / Free tier)
    geoapify_api_key: Optional[str] = Field(default=None, description="Geoapify API key for places search")

    # App environment & caching
    app_env: str = Field(default="development", description="Application environment (development/production)")
    cache_db_path: str = Field(default="travel_cache.db", description="SQLite path for HTTP response caching")
    request_timeout_seconds: float = Field(default=15.0, description="HTTP request timeout in seconds")
    user_agent: str = Field(
        default="TravelPlannerAgent/1.0 (academic-portfolio-project)",
        description="User-Agent header for OpenStreetMap / Nominatim polite requests",
    )

    # Tracing (Milestone 6)
    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith tracing")
    langchain_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langchain_project: str = Field(default="travel-planner-agent", description="LangSmith project name")


settings = Settings()
