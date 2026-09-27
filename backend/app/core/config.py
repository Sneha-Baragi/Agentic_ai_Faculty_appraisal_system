from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "sqlite:///./test.db"
    jwt_secret: str = Field(
        default="change-me-phase1-dev-secret",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_EXPIRE_MINUTES"),
    )
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = ""
    max_heal_attempts: int = 3
    cors_origins: str = "http://localhost:5173"
    seed_admin_email: str = "admin@demo.local"
    seed_admin_password: str = "admin-demo"
    seed_faculty_email: str = "faculty@demo.local"
    seed_faculty_password: str = "faculty-demo"
    seed_hod_email: str = "hod@demo.local"
    seed_hod_password: str = "hod-demo"
    seed_dean_email: str = "dean@demo.local"
    seed_dean_password: str = "dean-demo"
    seed_iqac_email: str = "iqac@demo.local"
    seed_iqac_password: str = "iqac-demo"
    seed_committee_email: str = "committee@demo.local"
    seed_committee_password: str = "committee-demo"
    storage_backend: str = "memory"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "faculty-evidence"
    minio_secure: bool = False
    max_upload_size: int = 10 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
