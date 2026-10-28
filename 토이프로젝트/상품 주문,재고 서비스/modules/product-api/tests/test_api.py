import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from redis.exceptions import ConnectionError as RedisConnectionError
from app.config import Settings
from app.database import Base
from app.main import create_app
from app.cache import ProductCache

ADMIN = {'X-API-Key': 'admin-test-key-123456789'}
INTERNAL = {'X-API-Key': 'internal-test-key-123456'}

class Cache:
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key)
    def set(self, value): self.values[value.id] = value
    def delete(self, key): self.values.pop(key, None)
    def close(self): pass

@pytest.fixture
def api():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    cache = Cache()
    settings = Settings(database_url='sqlite://', admin_api_key=ADMIN['X-API-Key'], internal_api_key=INTERNAL['X-API-Key'])
    with TestClient(create_app(settings, engine, cache)) as client:
        yield client, cache, engine
    engine.dispose()

def create(client, **extra):
    return client.post('/api/v1/admin/products', headers=ADMIN, json={'name': '키보드', 'price': 35000, **extra})

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

@pytest.mark.parametrize('payload', [{'name':'  '}, {'price':-1}, {'price':0.5}, {'price':10000000000}, {'status':'OTHER'}, {'extra':'no'}])
def test_validation(api, payload):
    assert create(api[0], **payload).status_code == 422

@pytest.mark.parametrize('payload', [{}, {'name':None}, {'price':None}, {'status':None}])
def test_patch_validation(api, payload):
    c, _, _ = api
    key = create(c).json()['id']
    assert c.patch(f'/api/v1/admin/products/{key}', headers=ADMIN, json=payload).status_code == 422

def test_auth(api):
    c, _, _ = api
    assert c.post('/api/v1/admin/products', json={'name':'A','price':1}).status_code == 401
    assert c.post('/api/v1/admin/products', headers=INTERNAL, json={'name':'A','price':1}).status_code == 403
    assert c.post('/internal/v1/products/lookup', headers=ADMIN, json={'product_ids':[1]}).status_code == 403

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

def test_limits_and_missing(api):
    c, _, _ = api
    assert c.get('/api/v1/products/999').status_code == 404
    assert c.get('/api/v1/products?size=101').status_code == 422
    assert c.post('/internal/v1/products/lookup', headers=INTERNAL, json={'product_ids':list(range(1,102))}).status_code == 422

def test_health_and_db_failure(api):
    c, _, engine = api
    assert c.get('/health/live').status_code == 200
    assert c.get('/health/ready').status_code == 200
    Base.metadata.drop_all(engine)
    response = c.get('/api/v1/products')
    assert response.status_code == 503
    assert 'SELECT' not in response.text

def test_redis_failure_falls_back(api):
    c, _, _ = api
    key = create(c).json()['id']
    cache = ProductCache('redis://localhost', 60)
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

def test_cached_read_does_not_need_db(api):
    c, _, engine = api
    key = create(c).json()['id']
    c.get(f'/api/v1/products/{key}')
    Base.metadata.drop_all(engine)
    assert c.get(f'/api/v1/products/{key}').status_code == 200

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

def test_database_constraints(api):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    _, _, engine = api
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO products (name, price, status, created_at, updated_at) VALUES ('A', -1, 'ON_SALE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
