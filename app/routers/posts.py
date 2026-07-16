from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def posts_ping():
    return {"ok": True}