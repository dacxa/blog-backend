from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def categories_ping():
    return {"ok": True}