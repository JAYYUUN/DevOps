from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_session

router = APIRouter(prefix='/health', tags=['health'])

@router.get('/live')
def live():
    return {'status': 'alive'}

@router.get('/ready')
def ready(session: Session = Depends(get_session)):
    session.execute(text('SELECT 1'))
    return {'status': 'ready'}
