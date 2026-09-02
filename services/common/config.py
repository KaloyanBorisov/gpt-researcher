import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Service discovery URLs
    GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "8000"))
    ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://research-orchestrator:8001")
    SCRAPER_URL: str = os.getenv("SCRAPER_URL", "http://scraper-service:8002")
    DOCUMENT_URL: str = os.getenv("DOCUMENT_URL", "http://document-service:8003")
    EXPORT_URL: str = os.getenv("EXPORT_URL", "http://export-service:8004")
    PLANNING_URL: str = os.getenv("PLANNING_URL", "http://planning-service:8011")
    SECTION_RESEARCH_URL: str = os.getenv("SECTION_RESEARCH_URL", "http://section-research-service:8012")
    REVIEWER_URL: str = os.getenv("REVIEWER_URL", "http://reviewer-service:8013")
    WRITER_URL: str = os.getenv("WRITER_URL", "http://writer-service:8014")

    # Redis message broker & Pub/Sub
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() in ("true", "1", "yes")

    # Object storage / Output directory
    OUTPUTS_DIR: str = os.getenv("OUTPUTS_DIR", "outputs")
    DOCS_DIR: str = os.getenv("DOCS_DIR", "my-docs")

    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

settings = ServiceSettings()

