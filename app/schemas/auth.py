from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


USERNAME_PATTERN = r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$"

# --- User Authentication Schemas ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, pattern=USERNAME_PATTERN, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码")

# 【新增】专门用于接收完整注册请求的模型（包含 code）
class UserRegister(UserCreate):
    code: str = Field(..., min_length=6, max_length=6, description="验证码")

class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class EmailVerificationRequest(BaseModel):
    email: EmailStr = Field(..., description="邮箱地址")

class EmailVerificationCheck(BaseModel):
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")

# --- JWT Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
