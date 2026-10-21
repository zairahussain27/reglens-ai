from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    env: str = "development"
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_days: int = 7
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'reglens.db'}"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 15
    google_client_id: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    embeddings: str = "fastembed"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    min_score: float = 0.2
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "reglens_chunks_v2"
    qdrant_timeout_seconds: int = 60
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    seed_dir: Path = BASE_DIR / "seed" / "regulations"
    frontend_dist: Path = BASE_DIR.parent / "frontend" / "dist"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "production" and s.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be set when ENV=production")
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    return s
