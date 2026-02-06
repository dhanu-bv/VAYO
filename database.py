from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:dhanu@localhost:5432/community_matching"
)

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class MatchTask(Base):
    __tablename__ = "match_tasks"

    task_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    status = Column(String, default="processing")
    result = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class Community(Base):
    __tablename__ = "communities"

    community_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String)
    member_count = Column(Integer, default=0)
    city = Column(String, nullable=False)
    timezone = Column(String, nullable=False)
    embedding_id = Column(String)  # exists in DB ✅
    created_at = Column(DateTime, default=datetime.utcnow)



class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    bio = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommunityMember(Base):
    __tablename__ = "community_members"

    user_id = Column(String, primary_key=True)
    community_id = Column(String, primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    auto_joined = Column(Boolean, default=False)


class CommunityActivity(Base):
    __tablename__ = "community_activity"

    message_id = Column(String, primary_key=True)
    community_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
