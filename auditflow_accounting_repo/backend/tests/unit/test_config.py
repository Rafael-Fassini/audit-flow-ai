import pytest
from pydantic import ValidationError

from app.core.config import ENV_FILES, PROJECT_ROOT, Settings, get_settings


def test_settings_reads_required_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", "custom/uploads")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.openai_api_key == "secret"
    assert settings.openai_model == "gpt-test"
    assert settings.app_port == 9000
    assert str(settings.upload_storage_dir) == "custom/uploads"


def test_settings_keeps_allowed_non_sensitive_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    settings = Settings(_env_file=None)

    assert settings.app_name == "AuditFlow AI Backend"
    assert settings.app_env == "development"
    assert settings.app_port == 8000
    assert str(settings.document_metadata_path) == "storage/document_metadata.json"
    assert str(settings.analysis_report_path) == "storage/analysis_reports.json"
    assert settings.embedding_vector_size == 64
    assert settings.retrieval_top_k == 5


def test_settings_errors_when_required_environment_is_missing(monkeypatch) -> None:
    for name in ("DATABASE_URL", "QDRANT_URL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    error_locations = {error["loc"][0] for error in exc_info.value.errors()}
    assert {
        "database_url",
        "qdrant_url",
        "openai_api_key",
        "openai_model",
    }.issubset(error_locations)


def test_get_settings_uses_central_cached_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.openai_model == "gpt-test"
    get_settings.cache_clear()


def test_default_env_files_include_project_root_env() -> None:
    assert ENV_FILES[0] == PROJECT_ROOT / ".env"
    assert ENV_FILES[1].name == ".env"
    assert ENV_FILES[1].parent.name == "backend"
