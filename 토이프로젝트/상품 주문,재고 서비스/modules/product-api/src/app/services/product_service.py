from fastapi import HTTPException
from sqlalchemy import select, func
from ..models.product import Product
from ..schemas.product import ProductRead, ProductPage, LookupProduct, LookupResponse

def find(session, product_id):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, 'Product not found')
    return product

def create(session, data):
    product = Product(**data.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)
    return ProductRead.model_validate(product)

def update(session, cache, product_id, data):
    # Lock the row to serialize concurrent updates in MariaDB.
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(404, 'Product not found')
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(product, name, value)
    session.commit()
    cache.delete(product_id)
    session.refresh(product)
    return ProductRead.model_validate(product)

def listing(session, page, size):
    query = select(Product).where(Product.status == 'ON_SALE')
    total = session.scalar(select(func.count()).select_from(Product).where(Product.status == 'ON_SALE'))
    products = session.scalars(query.order_by(Product.id.desc()).offset((page-1)*size).limit(size)).all()
    return ProductPage(items=[ProductRead.model_validate(p) for p in products], page=page, size=size, total=total)

def detail(session, cache, product_id):
    hit = cache.get(product_id)
    if hit is not None:
        return hit
    product = ProductRead.model_validate(find(session, product_id))
    cache.set(product)
    return product

def lookup(session, ids):
    ids = list(dict.fromkeys(ids))
    products = session.scalars(select(Product).where(Product.id.in_(ids))).all()
    by_id = {p.id: p for p in products}
    return LookupResponse(items=[LookupProduct.model_validate(by_id[i]) for i in ids if i in by_id], missing_ids=[i for i in ids if i not in by_id])
