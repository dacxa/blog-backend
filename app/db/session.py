from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.url import build_mysql_database_url


SQLALCHEMY_DATABASE_URL = build_mysql_database_url(
    username=settings.MYSQL_USER,
    password=settings.MYSQL_PASSWORD,
    host=settings.MYSQL_HOST,
    port=settings.MYSQL_PORT,
    database=settings.MYSQL_DB,
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
