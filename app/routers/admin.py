from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.models import Post, User
from app.db.session import get_db
from app.schemas.post import PostAdminResponse, ReviewPostRequest


router = APIRouter(prefix="/admin", tags=["administration"])


def admin_post_response(post: Post) -> PostAdminResponse:
    return PostAdminResponse(
        id=post.id,
        author_id=post.author_id,
        category_id=post.category_id,
        title=post.title,
        content=post.content,
        status=post.status,
        created_at=post.created_at,
        updated_at=post.updated_at,
        published_at=post.published_at,
        reviewed_by_id=post.reviewed_by_id,
        reviewed_at=post.reviewed_at,
        review_note=post.review_note,
    )


@router.get("/posts", response_model=list[PostAdminResponse])
def list_posts_for_review(
    post_status: Literal["pending", "published", "rejected"] | None = Query(
        default=None,
        alias="status",
    ),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PostAdminResponse]:
    query = db.query(Post)
    if post_status is not None:
        query = query.filter(Post.status == post_status)
    posts = query.order_by(Post.created_at.desc(), Post.id.desc()).all()
    return [admin_post_response(post) for post in posts]


@router.post("/posts/{post_id}/review", response_model=PostAdminResponse)
def review_post(
    post_id: int,
    payload: ReviewPostRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PostAdminResponse:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    reviewed_at = datetime.utcnow()
    result = db.execute(
        update(Post)
        .where(Post.id == post_id, Post.status == "pending")
        .values(
            status=payload.status,
            reviewed_by_id=current_admin.id,
            reviewed_at=reviewed_at,
            review_note=payload.note,
            published_at=reviewed_at if payload.status == "published" else None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending posts can be reviewed.",
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Post review could not be saved.",
        )

    post = db.get(Post, post_id)
    return admin_post_response(post)
