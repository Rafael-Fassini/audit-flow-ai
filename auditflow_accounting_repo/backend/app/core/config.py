from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AuditFlow AI Backend"
    app_env: str = "development"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/auditflow"
    qdrant_url: str = "http://localhost:6333"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    upload_storage_dir: Path = Path("storage/uploads")
    document_metadata_path: Path = Path("storage/document_metadata.json")
    max_upload_size_bytes: int = 10 * 1024 * 1024
    knowledge_collection_name: str = "auditflow_knowledge"
    embedding_vector_size: int = 64
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
