from sqlalchemy import URL


def build_mysql_database_url(
    *,
    username: str,
    password: str,
    host: str,
    port: int,
    database: str,
) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query={"charset": "utf8mb4"},
    )
