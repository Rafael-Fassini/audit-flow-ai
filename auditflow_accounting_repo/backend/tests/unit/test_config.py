import pytest
from pydantic import ValidationError

from app.core.config import ENV_FILES, PROJECT_ROOT, Settings, get_settings


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    monkeypatch.setenv("AGENT_MODEL", "gpt-agent-test")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.2")
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("AGENT_MAX_OUTPUT_TOKENS", "4096")


def test_settings_reads_required_environment_values(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", "custom/uploads")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.openai_api_key == "secret"
    assert settings.openai_model == "gpt-test"
    assert settings.agent_provider == "openai"
    assert settings.agent_model == "gpt-agent-test"
    assert settings.agent_temperature == 0.2
    assert settings.agent_timeout_seconds == 45
    assert settings.agent_max_output_tokens == 4096
    assert settings.app_port == 9000
    assert str(settings.upload_storage_dir) == "custom/uploads"


def test_settings_keeps_allowed_non_sensitive_defaults(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AuditFlow AI Backend"
    assert settings.app_env == "development"
    assert settings.app_port == 8000
    assert str(settings.document_metadata_path) == "storage/document_metadata.json"
    assert str(settings.analysis_report_path) == "storage/analysis_reports.json"
    assert settings.embedding_vector_size == 64
    assert settings.retrieval_top_k == 5


def test_settings_errors_when_required_environment_is_missing(monkeypatch) -> None:
    for name in (
        "DATABASE_URL",
        "QDRANT_URL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "AGENT_PROVIDER",
        "AGENT_MODEL",
        "AGENT_TEMPERATURE",
        "AGENT_TIMEOUT_SECONDS",
        "AGENT_MAX_OUTPUT_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    error_locations = {error["loc"][0] for error in exc_info.value.errors()}
    assert {
        "database_url",
        "qdrant_url",
        "openai_api_key",
        "openai_model",
        "agent_provider",
        "agent_model",
        "agent_temperature",
        "agent_timeout_seconds",
        "agent_max_output_tokens",
    }.issubset(error_locations)


def test_get_settings_uses_central_cached_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    _set_required_env(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.openai_model == "gpt-test"
    get_settings.cache_clear()


def test_agent_runtime_config_is_centralized_and_env_driven(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)
    config = settings.agent_runtime_config("risk_inference")

    assert config.agent_role == "risk_inference"
    assert config.provider == "openai"
    assert config.model == "gpt-agent-test"
    assert config.temperature == 0.2
    assert config.timeout_seconds == 45
    assert config.max_output_tokens == 4096


def test_settings_rejects_invalid_agent_config(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("AGENT_MODEL", "   ")
    monkeypatch.setenv("AGENT_TEMPERATURE", "3")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    error_locations = {error["loc"][0] for error in exc_info.value.errors()}
    assert {"agent_model", "agent_temperature"}.issubset(error_locations)


def test_default_env_files_include_project_root_env() -> None:
    assert ENV_FILES[0] == PROJECT_ROOT / ".env"
    assert ENV_FILES[1].name == ".env"
    assert ENV_FILES[1].parent.name == "backend"
