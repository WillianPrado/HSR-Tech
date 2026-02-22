import datetime

from sqlalchemy import UUID, Column, DateTime, Integer, String, Text, JSON, ForeignKey
from models.user import Base

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    audio_path = Column(String(255))      # Caminho do arquivo (opcional)
    transcript = Column(Text)            # Texto transcrito
    analysis = Column(JSON)              # Dados da análise (ex: {"sentiment": 0.8})
    title = Column(String)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )