# Kubernetes 상태 확인: 프로세스 생존과 DB를 사용할 준비 상태를 분리한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_session

router = APIRouter(prefix='/health', tags=['health'])

# DB·Redis 장애와 무관하게 앱이 응답하는지 확인한다. 불필요한 재시작을 줄인다.
@router.get('/live')
def live():
    return {'status': 'alive'}

# SELECT 1로 DB 연결을 확인한다. 실패하면 공통 예외 처리기가 503을 반환한다.
@router.get('/ready')
def ready(session: Session = Depends(get_session)):
    session.execute(text('SELECT 1'))
    return {'status': 'ready'}
