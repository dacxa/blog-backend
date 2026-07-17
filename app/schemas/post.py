from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=10, max_length=10000)
    category_id: int | None = None


class PostPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    category_id: int | None
    title: str
    content: str
    status: Literal["published"]
    created_at: datetime
    updated_at: datetime
    published_at: datetime


class PostMineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    category_id: int | None
    title: str
    content: str
    status: Literal["pending", "published", "rejected"]
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    review_note: str | None


class PostAdminResponse(PostMineResponse):
    pass


class ReviewPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["published", "rejected"]
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def rejected_post_requires_note(self) -> "ReviewPostRequest":
        if self.status == "rejected" and (self.note is None or not self.note.strip()):
            raise ValueError("A rejection review requires a non-empty note.")
        return self
