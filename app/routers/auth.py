from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import EmailVerificationRequest, UserRegister, UserLogin, Token
from app.services import verification_service

# 🎯 【精准修正】：这里将导入改为了你的 hash_password
from app.core.security import verify_password, create_access_token, hash_password
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["认证"])


# ==========================================
# 🚀 专为【诺玛前端系统】定制的数据模型与直通接口
# ==========================================
class NormaRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


@router.post("/register", summary="纯净直达注册 (无邮件验证版-适配诺玛系统)")
def direct_register(payload: NormaRegisterRequest, db: Session = Depends(get_db)):
    # 1. 血统查重：检查用户名或邮箱是否冲突
    user_exists = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()

    if user_exists:
        raise HTTPException(status_code=400, detail="档案已有记录，该血统编号或密级邮箱不可用")

    # 2. 编译言灵序列（调用你 security.py 里的 hash_password）
    hashed_pwd = hash_password(payload.password)

    # 3. 诺玛档案录入
    new_member = User(
        username=payload.username,
        email=payload.email,
        password_hash=hashed_pwd  # 存入哈希后的密文
    )

    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    # 4. 200 OK 响应，触发前端两秒绿字跳转！
    return {"msg": "诺玛系统：基因录入完成"}


# ==========================================
# 🛑 以下为你原本的注册邮件功能代码 (予以保留，日后开启邮件系统时可用)
# ==========================================

@router.post("/register/request-code", summary="发送注册验证码")
def request_code(payload: EmailVerificationRequest):
    verification_service.request_code(payload.email)
    return {"msg": "验证码已发送，请检查邮箱（包含垃圾箱）"}


@router.post("/register/verify-code", summary="验证并注册")
def verify_and_register(payload: UserRegister):
    verification_service.verify_and_create_user(
        email=payload.email,
        code=payload.code,
        username=payload.username,
        password=payload.password
    )
    return {"msg": "注册成功，请前往登录"}


# ==========================================
# 🔑 极度关键：登录接口修复 (将权利交还给数据库)
# 注意：我移除了 response_model=Token，用来让接口能多返回 role 字段给前端！！！
# ==========================================
# ==========================================
# 🔑 极度关键：登录接口修复 (动态下发权限，防止数据库缺字段报错)
# ==========================================
@router.post("/login", summary="用户登录与权限下发")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    # 1. 允许用户填入账号时，无论是 邮箱 还是 用户名 都能匹配
    user = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.username)
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="血统编号扫描失败或言灵序列错误")

    # 2. 签发门禁卡 (JWT Token)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(seconds=settings.JWT_ACCESS_EXPIRE_SECONDS)
    )

    # 3. 动态计算权限 (修复缺少 role 字段的报错)
    # 如果检测到是校长的特定邮箱，直接在后端内存中赋予 "admin" 权限！
    if user.email == "2191737256@qq.com" or user.username == "2191737256@qq.com":
        current_role = "admin"
        current_blood = "S"
    else:
        # getattr 安全获取：如果数据库没有 role 字段，就默认给 'user'，不会再崩溃了
        current_role = getattr(user, 'role', 'user')
        current_blood = getattr(user, 'blood_grade', 'A')

    # 4. 返还结果给前端
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": current_role,  # 诺玛(前端)现在能安全接到这个字段了
        "blood_grade": current_blood
    }