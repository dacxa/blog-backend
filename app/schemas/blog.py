from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- Category Schemas ---
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True # 兼容 SQLAlchemy ORM


# --- Post Schemas ---
class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="文章标题")
    content: str = Field(..., min_length=10, description="文章内容")
    category_id: Optional[int] = Field(None, description="文章分类ID")

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="文章标题")
    content: Optional[str] = Field(None, min_length=10, description="文章内容")
    category_id: Optional[int] = Field(None, description="文章分类ID")

class PostResponse(PostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime

    # 关联模型也可以通过 Pydantic 响应
    # 如果需要在PostResponse中直接显示Category或User的详细信息，可以在这里定义
    # 例如：category: Optional[CategoryResponse]
    # 但为了避免循环引用或过度暴露信息，通常只返回ID或者单独接口获取详情

    class Config:
        from_attributes = True


# --- Like Schemas ---
class LikeResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True

