from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

class Base(DeclarativeBase):
    pass

def make_engine(url):
    options = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {'connect_args': {'connect_timeout': 3}}
    return create_engine(url, pool_pre_ping=True, **options)

def get_session(request: Request):
    with request.app.state.sessions() as session:
        yield session
