from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from models.user import Base as UserBase

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    UserBase.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()