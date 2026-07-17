from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    Text, UniqueConstraint, Enum, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum(
            "user",
            "admin",
            name="user_role",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default="user",
        server_default="user",
    )
    token_version = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False, index=True)
    expire_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_status_published_at", "status", "published_at"),
    )

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(
        Enum(
            "pending",
            "published",
            "rejected",
            name="post_status",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])
    category = relationship("Category")


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_like_user_post"),
    )
