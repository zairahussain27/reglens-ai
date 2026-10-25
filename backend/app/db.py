from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")
engine_options = {
    "connect_args": {"check_same_thread": False} if _is_sqlite else {"prepare_threshold": None},
    "pool_pre_ping": True,
}
if not _is_sqlite:
    engine_options.update(pool_size=1, max_overflow=0, pool_recycle=300, pool_timeout=30, pool_use_lifo=True)
engine = create_engine(settings.database_url, **engine_options)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):  # WAL + FK enforcement for a safe, fast SQLite
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
