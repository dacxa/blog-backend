from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def likes_ping():
    return {"ok": True}