import datetime
from typing import Any

import jwt
from fastapi import HTTPException, status
import bcrypt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    校验密码
    """
    # bcrypt 运算需要 bytes 类型，所以先编码
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def hash_password(password: str) -> str:
    """
    加密密码
    """
    # 1. 生成盐值
    salt = bcrypt.gensalt()
    # 2. 结合密码用 bcrypt 加密
    hashed_pwd = bcrypt.hashpw(password.encode('utf-8'), salt)
    # 3. 把 bytes 转化为普通字符串返回，方便存入 MySQL 数据库
    return hashed_pwd.decode('utf-8')


def create_access_token(data: dict[str, Any], expires_delta: datetime.timedelta | None = None) -> str:
    """
    生成访问令牌 (JWT Token)
    """
    now = datetime.datetime.now(datetime.UTC)

    # 如果调用方传了明确的过期时间就用传的，否则用配置文件里的默认时间
    if expires_delta:
        exp = now + expires_delta
    else:
        exp = now + datetime.timedelta(seconds=settings.JWT_ACCESS_EXPIRE_SECONDS)

    # 拷贝 data 防止影响原字典，并合并 iat (签发时间) 和 exp (过期时间)
    payload = data.copy()
    payload.update({
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    })

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    解析并验证令牌
    """
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已过期")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效")
