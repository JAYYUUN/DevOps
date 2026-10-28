# 상품 처리 로직: DB 조회·저장과 캐시 사용 순서를 담당한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import HTTPException
from sqlalchemy import select, func
from ..models.product import Product
from ..schemas.product import ProductRead, ProductPage, LookupProduct, LookupResponse

# ID에 해당하는 상품이 없으면 공통으로 404를 반환한다.
def find(session, product_id):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, 'Product not found')
    return product

# 검증된 입력으로 상품을 생성하고 commit이 성공한 뒤 저장 결과를 반환한다.
def create(session, data):
    product = Product(**data.model_dump())
    session.add(product)
    session.commit()
    # DB에 저장된 최신 값을 다시 읽는다. 이 단계 실패 시 이미 저장되었을 수도 있다.
    session.refresh(product)
    return ProductRead.model_validate(product)

# 동일 상품의 수정 순서를 DB 잠금으로 제어하고 전달된 필드만 변경한다.
def update(session, cache, product_id, data):
    # Lock the row to serialize concurrent updates in MariaDB.
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(404, 'Product not found')
    # exclude_unset은 요청에 없는 필드를 제외한다. 명시한 description=null은 반영한다.
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(product, name, value)
    session.commit()
    # DB 저장이 성공한 뒤 캐시를 지워 다음 상세 조회가 원본을 다시 읽게 한다.
    cache.delete(product_id)
    # DB에 저장된 최신 값을 다시 읽는다. 이 단계 실패 시 이미 저장되었을 수도 있다.
    session.refresh(product)
    return ProductRead.model_validate(product)

# 판매 중 상품만 조회한다. 목록에는 캐시를 쓰지 않으며 페이지 범위를 적용한다.
def listing(session, page, size):
    query = select(Product).where(Product.status == 'ON_SALE')
    # 전체 건수와 현재 페이지 데이터는 별도 조회라 동시 변경 시 약간 다를 수 있다.
    total = session.scalar(select(func.count()).select_from(Product).where(Product.status == 'ON_SALE'))
    products = session.scalars(query.order_by(Product.id.desc()).offset((page-1)*size).limit(size)).all()
    return ProductPage(items=[ProductRead.model_validate(p) for p in products], page=page, size=size, total=total)

# 캐시가 있으면 즉시 반환하고 없으면 DB 원본을 읽어 다음 조회를 위해 저장한다.
def detail(session, cache, product_id):
    hit = cache.get(product_id)
    if hit is not None:
        return hit
    product = ProductRead.model_validate(find(session, product_id))
    cache.set(product)
    return product

# 주문 검증용 조회는 캐시를 거치지 않는다. 판매 중지 상품도 상태 확인용으로 반환한다.
def lookup(session, ids):
    # 중복 ID는 제거하되 처음 요청한 순서는 유지한다.
    ids = list(dict.fromkeys(ids))
    products = session.scalars(select(Product).where(Product.id.in_(ids))).all()
    # DB의 반환 순서에 의존하지 않고 요청 순서대로 상품과 누락 ID를 구성한다.
    by_id = {p.id: p for p in products}
    return LookupResponse(items=[LookupProduct.model_validate(by_id[i]) for i in ids if i in by_id], missing_ids=[i for i in ids if i not in by_id])
