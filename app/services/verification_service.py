from datetime import datetime, timedelta
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db.models import User, EmailVerification
from app.services.email_service import generate_code, send_verification_code


def request_code(email: str) -> None:
    """
    请求验证码（已移除 Redis，纯 MySQL 实现）
    """
    code = generate_code()

    # 获取设置中的过期秒数（默认 300 秒 = 5 分钟）
    expire_seconds = getattr(settings, "VERIFICATION_EXPIRE_SECONDS", 300)
    # 【完美解决】直接使用 timedelta 进行时间加法，彻底避开时间戳带来的时区错乱问题！
    expire_dt = datetime.utcnow() + timedelta(seconds=expire_seconds)

    with SessionLocal() as db:
        # 查找这名用户的验证码记录（倒序查找最新的一条）
        existing = db.query(EmailVerification).filter(EmailVerification.email == email).order_by(
            EmailVerification.id.desc()).first()

        if existing:
            # 如果之前请求过，我们这里不去限制频率，而是直接覆盖旧验证码
            existing.code = code
            existing.expire_at = expire_dt
            existing.used_at = None  # 重置使用状态
        else:
            # 第一次请求验证码，新建记录
            db.add(EmailVerification(email=email, code=code, expire_at=expire_dt))

        db.commit()

    # 存入数据库后，调用发邮件服务
    send_verification_code(email, code)


def verify_and_create_user(email: str, code: str, username: str, password: str) -> None:
    """
    校验验证码并创建用户
    """
    with SessionLocal() as db:
        v = (
            db.query(EmailVerification)
            .filter(EmailVerification.email == email)
            .order_by(EmailVerification.id.desc())
            .first()
        )

        if not v:
            raise HTTPException(status_code=400, detail="未请求验证码")

        if v.used_at is not None:
            raise HTTPException(status_code=400, detail="验证码已使用")

        if v.code != code:
            raise HTTPException(status_code=400, detail="验证码错误")

        if v.expire_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="验证码已过期")

        # 检查是否重复注册（检查用户名或邮箱）
        exists_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if exists_user:
            raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

        # 数据全部校验通过，创建新用户
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)

        # 标记验证码已使用
        v.used_at = datetime.utcnow()
        db.commit()