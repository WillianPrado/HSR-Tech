import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from models.user import Base as UserBase
from models import conversation
from models import message
from models import payment_event
from models import invoice

logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _run_migrations() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini_path = root_dir / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini_path}")

    alembic_cfg = Config(str(alembic_ini_path))
    command.upgrade(alembic_cfg, "head")


def init_db() -> None:
    try:
        _run_migrations()
        logger.info("Database migrations applied successfully.")
    except Exception as exc:
        logger.warning(f"Migration failed, falling back to create_all: {exc}")
        UserBase.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()