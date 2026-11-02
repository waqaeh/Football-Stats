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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
