import secrets
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

header = APIKeyHeader(name='X-API-Key', auto_error=False)

def check(request, supplied, setting):
    if supplied is None:
        raise HTTPException(401, 'API key required')
    expected = getattr(request.app.state.settings, setting).get_secret_value()
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(403, 'Invalid API key')

def require_admin(request: Request, key: str | None = Security(header)):
    check(request, key, 'admin_api_key')

def require_internal(request: Request, key: str | None = Security(header)):
    check(request, key, 'internal_api_key')
