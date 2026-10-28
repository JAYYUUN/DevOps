# 관리자 HTTP 경로: 인증 후 상품 등록·수정을 서비스 함수에 위임한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_session
from ..schemas.product import ProductCreate, ProductUpdate, ProductRead
from ..services import product_service as service

# 이 라우터의 모든 API에 관리자 키 검사를 공통 적용한다.
router = APIRouter(prefix='/api/v1/admin/products', tags=['admin'], dependencies=[Depends(require_admin)])

# 등록 성공은 201이다. 요청 본문은 ProductCreate가 먼저 검증한다.
@router.post('', response_model=ProductRead, status_code=201)
def create(data: ProductCreate, session: Session = Depends(get_session)):
    return service.create(session, data)

# 수정은 200이다. 상품 ID는 양수만 허용하고 앱의 공통 캐시를 전달한다.
@router.patch('/{product_id}', response_model=ProductRead)
def update(data: ProductUpdate, request: Request, product_id: int = Path(gt=0), session: Session = Depends(get_session)):
    return service.update(session, request.app.state.cache, product_id, data)
