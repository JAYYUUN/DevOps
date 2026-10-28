from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_session
from ..schemas.product import ProductCreate, ProductUpdate, ProductRead
from ..services import product_service as service

router = APIRouter(prefix='/api/v1/admin/products', tags=['admin'], dependencies=[Depends(require_admin)])

@router.post('', response_model=ProductRead, status_code=201)
def create(data: ProductCreate, session: Session = Depends(get_session)):
    return service.create(session, data)

@router.patch('/{product_id}', response_model=ProductRead)
def update(data: ProductUpdate, request: Request, product_id: int = Path(gt=0), session: Session = Depends(get_session)):
    return service.update(session, request.app.state.cache, product_id, data)
