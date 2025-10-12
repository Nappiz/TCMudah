from sqlalchemy import Column, String, Enum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
import enum
from .db import Base

class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    mentor = "mentor"
    peserta = "peserta"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    nim = Column(String, nullable=True)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, server_default="peserta")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
