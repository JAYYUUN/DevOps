# 사용자 조회 경로: 상품 목록과 상세 정보를 HTTP로 제공한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session
from ..database import get_session
from ..schemas.product import ProductRead, ProductPage
from ..services import product_service as service

# 사용자 조회는 현재 인증 없이 제공한다. 관리자·내부 경로와 구분한다.
router = APIRouter(prefix='/api/v1/products', tags=['products'])

# 페이지는 1부터, 크기는 1~100이다. 검증 실패는 FastAPI가 422로 응답한다.
@router.get('', response_model=ProductPage)
def listing(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    return service.listing(session, page, size)

# 상세 조회는 캐시를 사용할 수 있다. 양수가 아닌 ID는 요청 단계에서 거부한다.
@router.get('/{product_id}', response_model=ProductRead)
def detail(request: Request, product_id: int = Path(gt=0), session: Session = Depends(get_session)):
    return service.detail(session, request.app.state.cache, product_id)
