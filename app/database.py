import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./server_activity_logs.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# 幂等迁移：为已存在的旧库补全新列（create_all 不会修改已存在的表）。
# 覆盖 SQLite 与 PostgreSQL 两种方言。
_MIGRATIONS = {
    "activity_logs": [
        ("device_id", "VARCHAR(128)"),
        ("confidence", "FLOAT"),
        ("decision_source", "VARCHAR(32)"),
        ("reason", "VARCHAR(64)"),
        ("process", "VARCHAR(128)"),
        ("title", "VARCHAR(512)"),
    ],
    "image_analyses": [
        ("image_hash", "VARCHAR(64)"),
    ],
    "screenshots": [
        ("vision_label", "VARCHAR(32)"),
    ],
}

# 兼容旧库：image_base64 由 NOT NULL 放宽为可空（截图默认不再入库，只存哈希）。
# PostgreSQL 用 ALTER COLUMN DROP NOT NULL；SQLite 不支持该语法，忽略（开发库可重建）。
_ALTER_COLUMNS = {
    "image_analyses": [
        ("image_base64", "DROP NOT NULL"),
    ],
}


def migrate_schema():
    """为旧库补齐新增列；新库无需操作（create_all 已含全量定义）。"""
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    except Exception:
        return
    for table, cols in _MIGRATIONS.items():
        if table not in tables:
            continue
        try:
            existing = {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            continue
        with engine.begin() as conn:
            for col, coltype in cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))

    # NOT NULL 放宽（幂等：重复执行会因约束已放宽而无副作用）
    for table, ops in _ALTER_COLUMNS.items():
        if table not in tables:
            continue
        for col, op in ops:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {col} {op}"))
            except Exception:
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
