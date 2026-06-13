import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://mr_admin:mr_secret@localhost:5432/mr_visit"
    app_env: str = "development"
    # For demo: MR identity passed as header, hardcoded default for convenience
    default_mr_id: str = "00000000-0000-0000-0000-000000000001"

    class Config:
        env_file = ".env"


settings = Settings()
