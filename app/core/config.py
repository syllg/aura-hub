from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Aura Hub API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    database_url: str = "sqlite+aiosqlite:///./data/aura_hub.db"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "aura_hub_sop_chunks"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)

    llm_enabled: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_temperature: float = Field(default=1.0, ge=0, le=2)

    max_document_size_mb: int = Field(default=10, ge=1)
    max_csv_size_mb: int = Field(default=5, ge=1)
    chunk_target_tokens: int = Field(default=420, ge=100)
    chunk_max_tokens: int = Field(default=520, ge=100)
    chunk_overlap_tokens: int = Field(default=60, ge=0)
    rag_dense_candidates: int = Field(default=12, ge=3)
    rag_top_k: int = Field(default=3, ge=1, le=3)
    rag_min_final_score: float = Field(default=0.35, ge=0, le=1)

    anomaly_modified_z_threshold: float = Field(default=3.5, gt=0)
    anomaly_iqr_multiplier: float = Field(default=1.5, gt=0)
    anomaly_min_rows: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_locked_contract(self) -> Settings:
        if self.embedding_model != "text-embedding-3-small":
            raise ValueError("EMBEDDING_MODEL must be text-embedding-3-small")
        if self.embedding_dimensions != 1536:
            raise ValueError("EMBEDDING_DIMENSIONS must be 1536")
        if self.llm_model != "gpt-4o-mini":
            raise ValueError("LLM_MODEL must be gpt-4o")
        if self.chunk_max_tokens < self.chunk_target_tokens:
            raise ValueError("CHUNK_MAX_TOKENS must be >= CHUNK_TARGET_TOKENS")
        if self.chunk_overlap_tokens >= self.chunk_target_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be below target")
        return self

    @property
    def is_test(self) -> bool:
        return self.app_env.lower() == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
