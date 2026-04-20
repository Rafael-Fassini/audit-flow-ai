from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
ENV_FILES = (PROJECT_ROOT / ".env", BACKEND_ROOT / ".env")


class AgentRuntimeConfig(BaseModel):
    agent_role: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    timeout_seconds: int = Field(ge=1, le=600)
    max_output_tokens: int = Field(ge=1, le=200000)

    @field_validator("agent_role", "provider", "model")
    @classmethod
    def normalize_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


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
    analysis_report_path: Path = Path("storage/analysis_reports.json")
    max_upload_size_bytes: int = 10 * 1024 * 1024
    knowledge_collection_name: str = "auditflow_knowledge"
    embedding_vector_size: int = 64
    retrieval_top_k: int = 5
    agent_provider: str = Field(min_length=1)
    agent_model: str = Field(min_length=1)
    agent_temperature: float = Field(ge=0.0, le=2.0)
    agent_timeout_seconds: int = Field(ge=1, le=600)
    agent_max_output_tokens: int = Field(ge=1, le=200000)

    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    @field_validator("agent_provider", "agent_model")
    @classmethod
    def normalize_required_agent_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    def agent_runtime_config(self, agent_role: str) -> AgentRuntimeConfig:
        return AgentRuntimeConfig(
            agent_role=agent_role,
            provider=self.agent_provider,
            model=self.agent_model,
            temperature=self.agent_temperature,
            timeout_seconds=self.agent_timeout_seconds,
            max_output_tokens=self.agent_max_output_tokens,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
