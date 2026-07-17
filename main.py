from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
# 使用绝对路径导入你的项目模块
from app.routers import admin, auth, posts

# ==========================================
# 1. 初始化数据库表结构
# ==========================================

# ==========================================
# 2. 创建 FastAPI 实例
# ==========================================
app = FastAPI(title="My Blog API", description="我的个人网站后端接口", version="1.0.0")

# ==========================================
# 3. 配置全局中间件 (CORS 跨域配置)
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ==========================================
# 4. 挂载路由 (将其他模块的接口汇总到这里)
# ==========================================
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(admin.router)

# ==========================================
# 5. 基础接口
# ==========================================
@app.get("/", tags=["健康检查"])
def root():
    return {"status": "ok", "message": "Welcome to My Blog API!"}

# ==========================================
# 6. 本地运行配置
# ==========================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
