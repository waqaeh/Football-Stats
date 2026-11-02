from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    test_database_url: str | None = None
    football_data_api_key: str | None = None
    # Signs login tokens. Anyone who knows it can log in as anyone, so set a long random one in production.
    jwt_secret: str = "dev-only-secret-change-me"
    access_token_minutes: int = 60 * 24
    # How slow password hashing is (each +1 doubles it). Slow makes stolen hashes hard to crack.
    bcrypt_rounds: int = 12
    # Rules Q&A (RAG). "ollama" writes answers with a local model; "none" only returns the matching passages.
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    embedding_cache_dir: str | None = None  # where the embedding model is stored (None: a temp folder)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", "test_database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str | None) -> str | None:
        # Hosts like Neon hand out "postgresql://..." URLs; SQLAlchemy needs to be told to use psycopg 3.
        if url and url.startswith(("postgresql://", "postgres://")):
            return "postgresql+psycopg://" + url.split("://", 1)[1]
        return url


settings = Settings()
