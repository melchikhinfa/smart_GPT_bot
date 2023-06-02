import asyncio
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime
import os

Base = declarative_base()
db_str = f"postgresql://{os.getenv('db_user')}:{os.getenv('db_password')}@{os.getenv('db_host')}/{os.getenv('db_name')}"

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


async def async_init_db(uri):
    engine = create_async_engine(uri)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def async_save_message(engine, username, message, user_id, timestamp):
    async with AsyncSession(engine) as session:
        session.add(Message(id=user_id, username=username, message=message, timestamp=timestamp))
        await session.commit()


async def async_get_messages(engine):
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Message).order_by(Message.timestamp.desc()))
        return result.scalars().all()


# Usage

async def main(username, message, id):

    db_engine = await async_init_db(db_str)

    # Save a new message
    await async_save_message(db_engine, 'John', 'Hello, world!')

    # Get all messages
    messages = await async_get_messages(db_engine)
    for msg in messages:
        print(f'[{msg.timestamp}] {msg.username}: {msg.message}')


