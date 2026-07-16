from typing import Optional

from pydantic import EmailStr, Field # <--- 修改这里
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_BASE_URL: str = "http://localhost:8000"

    # --- Database Settings ---
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str

    # --- JWT Settings ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_SECONDS: int = 7776000 # 90天 (60 * 60 * 24 * 90)

    # --- Email Settings ---
    MAIL_USERNAME: str
    MAIL_PASSWORD: str # 邮箱授权码
    MAIL_FROM: EmailStr = Field(..., description="发件人邮箱")
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.qq.com" # QQ邮箱的SMTP服务器
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    # --- Verification Code Settings ---
    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 5 # 验证码有效期5分钟
settings = Settings()
