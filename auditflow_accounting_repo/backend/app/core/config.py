from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AuditFlow AI Backend"
    app_env: str = "development"
    app_port: int = 8000
    database_url: str = Field(min_length=1)
    qdrant_url: str = Field(min_length=1)
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(min_length=1)
    upload_storage_dir: Path = Path("storage/uploads")
    document_metadata_path: Path = Path("storage/document_metadata.json")
    max_upload_size_bytes: int = 10 * 1024 * 1024
    knowledge_collection_name: str = "auditflow_knowledge"
    embedding_vector_size: int = 64
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
