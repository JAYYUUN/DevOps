from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth import require_internal
from ..database import get_session
from ..schemas.product import LookupRequest, LookupResponse
from ..services import product_service as service

router = APIRouter(prefix='/internal/v1/products', tags=['internal'], dependencies=[Depends(require_internal)])

@router.post('/lookup', response_model=LookupResponse)
def lookup(data: LookupRequest, session: Session = Depends(get_session)):
    return service.lookup(session, data.product_ids)
