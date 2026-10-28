# 상세 조회 캐시: Redis가 실패해도 DB 조회와 상품 수정을 계속할 수 있게 한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

import logging
from redis import Redis
from redis.exceptions import RedisError
from pydantic import ValidationError
from .schemas.product import ProductRead

log = logging.getLogger(__name__)

# 키 형식과 저장 방식, 장애 처리 방식을 한곳에서 관리한다.
class ProductCache:
    # Redis 응답을 문자열로 받고 접속·응답 대기를 각각 0.5초로 제한한다.
    def __init__(self, url, ttl):
        self.client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5)
        self.ttl = ttl

    # 상품 ID로 캐시를 읽고 응답 모델로 검증한다. 누락·오류면 None을 반환한다.
    def get(self, product_id):
        try:
            raw = self.client.get(f'product:detail:{product_id}')
            return ProductRead.model_validate_json(raw) if raw else None
        # Redis 장애나 잘못된 캐시 데이터는 DB에서 다시 읽도록 처리한다.
        except (RedisError, ValidationError, ValueError):
            log.warning('Product cache read failed; using database')
            return None

    # 응답을 JSON으로 바꿔 TTL과 함께 저장한다. 캐시 저장 실패로 API를 실패시키지 않는다.
    def set(self, product):
        try:
            self.client.setex(f'product:detail:{product.id}', self.ttl, product.model_dump_json())
        except RedisError:
            log.warning('Product cache write failed')

    # DB 수정이 끝난 뒤 기존 캐시를 지운다. 실패하면 TTL 만료 때까지 이전 값이 남을 수 있다.
    def delete(self, product_id):
        try:
            self.client.delete(f'product:detail:{product_id}')
        except RedisError:
            log.warning('Product cache invalidation failed; waiting for TTL')

    # 앱이 종료될 때 Redis 연결을 정리한다.
    def close(self):
        self.client.close()
