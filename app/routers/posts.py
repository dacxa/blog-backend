from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import Category, Post, User
from app.db.session import get_db
from app.schemas.post import PostCreate, PostMineResponse, PostPublicResponse


router = APIRouter(prefix="/posts", tags=["posts"])


def public_post_response(post: Post) -> PostPublicResponse:
    return PostPublicResponse(
        id=post.id,
        author_id=post.author_id,
        category_id=post.category_id,
        title=post.title,
        content=post.content,
        status="published",
        created_at=post.created_at,
        updated_at=post.updated_at,
        published_at=post.published_at,
    )


def mine_post_response(post: Post) -> PostMineResponse:
    return PostMineResponse(
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


@router.get("", response_model=list[PostPublicResponse])
def list_published_posts(db: Session = Depends(get_db)) -> list[PostPublicResponse]:
    posts = (
        db.query(Post)
        .filter(Post.status == "published")
        .order_by(Post.published_at.desc(), Post.id.desc())
        .all()
    )
    return [public_post_response(post) for post in posts]


@router.post("", response_model=PostMineResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostMineResponse:
    if payload.category_id is not None and db.get(Category, payload.category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Category not found.",
        )

    post = Post(
        author_id=current_user.id,
        category_id=payload.category_id,
        title=payload.title,
        content=payload.content,
        status="pending",
    )
    db.add(post)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Post could not be created with the provided data.",
        )
    db.refresh(post)
    return mine_post_response(post)


@router.get("/mine", response_model=list[PostMineResponse])
def list_my_posts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PostMineResponse]:
    posts = (
        db.query(Post)
        .filter(Post.author_id == current_user.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .all()
    )
    return [mine_post_response(post) for post in posts]
