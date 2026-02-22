import datetime
import uuid

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, Text

from models.user import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID, ForeignKey("conversations.id"))
    role = Column(String)  # user | assistant | system
    content = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )