from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    audio_path = Column(String(255))      # Caminho do arquivo (opcional)
    transcript = Column(Text)            # Texto transcrito
    analysis = Column(JSON)              # Dados da análise (ex: {"sentiment": 0.8})