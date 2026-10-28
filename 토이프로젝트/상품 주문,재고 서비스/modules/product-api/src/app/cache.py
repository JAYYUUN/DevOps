import logging
from redis import Redis
from redis.exceptions import RedisError
from pydantic import ValidationError
from .schemas.product import ProductRead

log = logging.getLogger(__name__)

class ProductCache:
    def __init__(self, url, ttl):
        self.client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5)
        self.ttl = ttl

    def get(self, product_id):
        try:
            raw = self.client.get(f'product:detail:{product_id}')
            return ProductRead.model_validate_json(raw) if raw else None
        except (RedisError, ValidationError, ValueError):
            log.warning('Product cache read failed; using database')
            return None

    def set(self, product):
        try:
            self.client.setex(f'product:detail:{product.id}', self.ttl, product.model_dump_json())
        except RedisError:
            log.warning('Product cache write failed')

    def delete(self, product_id):
        try:
            self.client.delete(f'product:detail:{product_id}')
        except RedisError:
            log.warning('Product cache invalidation failed; waiting for TTL')

    def close(self):
        self.client.close()
