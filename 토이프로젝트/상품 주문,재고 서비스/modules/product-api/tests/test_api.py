# 상품 API 회귀 테스트: 정상 처리뿐 아니라 인증·검증·의존 서비스 실패도 확인한다.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from redis.exceptions import ConnectionError as RedisConnectionError
from app.config import Settings
from app.database import Base
from app.main import create_app
from app.cache import ProductCache

# 테스트 전용 고정 키다. 운영 Secret으로 사용하지 않는다.
ADMIN = {'X-API-Key': 'admin-test-key-123456789'}
INTERNAL = {'X-API-Key': 'internal-test-key-123456'}

# 외부 Redis 없이 캐시 적중·삭제를 검증하기 위한 메모리 대체 구현이다.
class Cache:
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key)
    def set(self, value): self.values[value.id] = value
    def delete(self, key): self.values.pop(key, None)
    def close(self): pass

# 테스트마다 새 메모리 DB와 캐시를 준비해 다른 테스트의 데이터가 섞이지 않게 한다.
@pytest.fixture
def api():
    # StaticPool로 같은 SQLite 메모리 DB를 모든 테스트 요청에서 공유한다.
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    cache = Cache()
    settings = Settings(database_url='sqlite://', admin_api_key=ADMIN['X-API-Key'], internal_api_key=INTERNAL['X-API-Key'])
    # 앱 시작·종료 수명주기도 실행한다. 실제 MariaDB 잠금 동작까지 검증하는 것은 아니다.
    with TestClient(create_app(settings, engine, cache)) as client:
        yield client, cache, engine
    engine.dispose()

# 등록 요청의 반복 코드를 모은 도우미다. extra로 특정 검증 항목을 바꿀 수 있다.
def create(client, **extra):
    return client.post('/api/v1/admin/products', headers=ADMIN, json={'name': '키보드', 'price': 35000, **extra})

# 등록 기본값·판매 상태 변경·목록 노출·캐시 삭제가 함께 올바르게 동작하는지 확인한다.
def test_crud_and_cache(api):
    c, cache, _ = api
    response = create(c)
    assert response.status_code == 201
    p = response.json(); key = p['id']
    assert p['status'] == 'STOPPED'
    assert c.get('/api/v1/products').json()['total'] == 0
    assert c.get(f'/api/v1/products/{key}').status_code == 200
    assert key in cache.values
    patch = c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json={'status':'ON_SALE', 'price':40000})
    assert patch.status_code == 200
    assert key not in cache.values
    assert c.get('/api/v1/products').json()['total'] == 1
    assert c.get(f'/api/v1/products/{key}').json()['price'] == '40000.00'
    assert c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json={'description':None}).status_code == 200

# 여러 잘못된 입력을 각각 독립된 테스트 사례로 실행한다.
@pytest.mark.parametrize('payload', [{'name':'  '}, {'price':-1}, {'price':0.5}, {'price':10000000000}, {'status':'OTHER'}, {'extra':'no'}])
# 잘못된 이름·금액·상태·추가 필드가 422로 거부되는지 확인한다.
def test_validation(api, payload):
    assert create(api[0], **payload).status_code == 422

# 여러 잘못된 입력을 각각 독립된 테스트 사례로 실행한다.
@pytest.mark.parametrize('payload', [{}, {'name':None}, {'price':None}, {'status':None}])
# 빈 수정과 필수 필드 null 변경을 거부하는지 확인한다.
def test_patch_validation(api, payload):
    c, _, _ = api
    key = create(c).json()['id']
    assert c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json=payload).status_code == 422

# 키 누락은 401, 용도가 다른 키는 403인지 확인한다.
def test_auth(api):
    c, _, _ = api
    assert c.post('/api/v1/admin/products', json={'name':'A','price':1}).status_code == 401
    assert c.post('/api/v1/admin/products', headers=INTERNAL, json={'name':'A','price':1}).status_code == 403
    assert c.post('/internal/v1/products/lookup', headers=ADMIN, json={'product_ids':[1]}).status_code == 403

# 의도적으로 오래된 캐시를 남겨도 내부 조회는 최신 DB 가격을 사용하는지 확인한다.
def test_internal_bypasses_stale_cache(api):
    c, cache, _ = api
    key = create(c).json()['id']
    c.get(f'/api/v1/products/{key}')
    stale = cache.values[key]
    c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json={'price':100})
    cache.values[key] = stale
    result = c.post('/internal/v1/products/lookup', headers=INTERNAL, json={'product_ids':[key,999,key]}).json()
    assert result['items'][0]['price'] == '100.00'
    assert len(result['items']) == 1
    assert result['missing_ids'] == [999]

# 없는 상품과 페이지·일괄 조회 개수 제한을 확인한다.
def test_limits_and_missing(api):
    c, _, _ = api
    assert c.get('/api/v1/products/999').status_code == 404
    assert c.get('/api/v1/products?size=101').status_code == 422
    assert c.post('/internal/v1/products/lookup', headers=INTERNAL, json={'product_ids':list(range(1,102))}).status_code == 422

# DB 쿼리를 실패시켜 503 응답에 SQL 내용이 노출되지 않는지 확인한다.
def test_health_and_db_failure(api):
    c, _, engine = api
    assert c.get('/health/live').status_code == 200
    assert c.get('/health/ready').status_code == 200
    Base.metadata.drop_all(engine)
    response = c.get('/api/v1/products')
    assert response.status_code == 503
    assert 'SELECT' not in response.text

# Redis 읽기·쓰기·삭제를 모두 실패시켜도 조회·수정이 성공하는지 확인한다.
def test_redis_failure_falls_back(api):
    c, _, _ = api
    key = create(c).json()['id']
    cache = ProductCache('redis://localhost', 60)
    # Redis 접속 오류를 의도적으로 발생시키는 대체 클라이언트다.
    class Broken:
        def get(self, *a): raise RedisConnectionError()
        def setex(self, *a): raise RedisConnectionError()
        def delete(self, *a): raise RedisConnectionError()
        def close(self): pass
    cache.client.close()
    cache.client = Broken()
    c.app.state.cache = cache
    assert c.get(f'/api/v1/products/{key}').status_code == 200
    assert c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json={'price':200}).status_code == 200

# 캐시가 준비되어 있으면 DB 테이블이 없어도 해당 상세 응답을 반환하는지 확인한다.
def test_cached_read_does_not_need_db(api):
    c, _, engine = api
    key = create(c).json()['id']
    c.get(f'/api/v1/products/{key}')
    Base.metadata.drop_all(engine)
    assert c.get(f'/api/v1/products/{key}').status_code == 200

# DB 접근 실패 시 ready는 503이고 live는 계속 200인지 확인한다.
def test_ready_failure_keeps_live(api):
    from app.database import get_session
    from sqlalchemy.exc import OperationalError
    c, _, _ = api
    class BrokenSession:
        def execute(self, *args):
            raise OperationalError('SELECT 1', {}, Exception('unavailable'))
    c.app.dependency_overrides[get_session] = lambda: BrokenSession()
    assert c.get('/health/ready').status_code == 503
    assert c.get('/health/live').status_code == 200

# API 검증 외에도 DB 제약조건이 음수 가격 저장을 거부하는지 확인한다.
def test_database_constraints(api):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    _, _, engine = api
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO products (name, price, status, created_at, updated_at) VALUES ('A', -1, 'ON_SALE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
