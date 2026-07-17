from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "https://solocraft.xyz"

    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_SECONDS: int = 8 * 60 * 60
    SESSION_COOKIE_SECURE: bool = True

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: EmailStr = Field(..., description="Sender email address")
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.qq.com"
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 5
    VERIFICATION_CODE_RESEND_SECONDS: int = 60

    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise ValueError("CORS_ORIGINS must contain explicit origins when credentials are enabled.")
        return origins


settings = Settings()
