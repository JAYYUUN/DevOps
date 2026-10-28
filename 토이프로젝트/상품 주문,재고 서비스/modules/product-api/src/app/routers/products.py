from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session
from ..database import get_session
from ..schemas.product import ProductRead, ProductPage
from ..services import product_service as service

router = APIRouter(prefix='/api/v1/products', tags=['products'])

@router.get('', response_model=ProductPage)
def listing(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    return service.listing(session, page, size)

@router.get('/{product_id}', response_model=ProductRead)
def detail(request: Request, product_id: int = Path(gt=0), session: Session = Depends(get_session)):
    return service.detail(session, request.app.state.cache, product_id)
