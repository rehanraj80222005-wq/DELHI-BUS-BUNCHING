import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings
from src.database.models import Base

logger = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def get_engine(database_url: str = None):
    global _engine
    url = database_url or settings.db.url

    # Check if postgres driver is available or if fallback needed
    fallback_sqlite = f"sqlite:///{settings.paths.data_dir}/delhi_transit.db"
    
    if url.startswith("postgresql"):
        try:
            import psycopg  # noqa
        except ImportError:
            try:
                import psycopg2  # noqa
            except ImportError:
                logger.warning("PostgreSQL driver (psycopg/psycopg2) not installed. Falling back to local SQLite.")
                url = fallback_sqlite

    # Ensure parent directory exists for SQLite
    if url.startswith("sqlite"):
        from pathlib import Path
        db_path = url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}

    try:
        _engine = create_engine(
            url,
            echo=settings.db.echo,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        # Test connection
        with _engine.connect():
            pass
    except Exception as exc:
        if url != fallback_sqlite:
            logger.warning("Could not connect to configured DB (%s). Falling back to SQLite: %s", exc, fallback_sqlite)
            url = fallback_sqlite
            from pathlib import Path
            Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(
                url,
                echo=settings.db.echo,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )

    return _engine


def get_session(database_url: str = None) -> Session:
    global _SessionFactory
    if _SessionFactory is None or database_url is not None:
        engine = get_engine(database_url)
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionFactory()


def init_db(database_url: str = None) -> None:
    engine = get_engine(database_url)
    logger.info("Initializing database tables on %s", engine.url)
    Base.metadata.create_all(bind=engine)
