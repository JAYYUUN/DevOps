# 서비스 간 조회 경로: 주문 API에 DB 원본 상품 정보를 제공한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth import require_internal
from ..database import get_session
from ..schemas.product import LookupRequest, LookupResponse
from ..services import product_service as service

# 내부 전용 키 검사를 적용한다. internal이라는 경로 이름만으로 보호되는 것은 아니다.
router = APIRouter(prefix='/internal/v1/products', tags=['internal'], dependencies=[Depends(require_internal)])

# 조회할 ID 목록을 JSON 본문으로 받기 위해 POST를 사용한다. 데이터를 변경하지 않는다.
@router.post('/lookup', response_model=LookupResponse)
def lookup(data: LookupRequest, session: Session = Depends(get_session)):
    return service.lookup(session, data.product_ids)
