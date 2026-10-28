# API 키 인증: 관리자 작업과 주문 서비스의 내부 조회 권한을 분리한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

import secrets
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

# 요청 헤더 X-API-Key를 읽는다. 누락 오류는 아래에서 직접 401로 응답한다.
header = APIKeyHeader(name='X-API-Key', auto_error=False)

# 인증 공통 함수: 키가 없으면 401, 틀리거나 다른 용도의 키이면 403이다.
def check(request, supplied, setting):
    if supplied is None:
        raise HTTPException(401, 'API key required')
    # 요청한 권한에 맞는 서버 측 키만 꺼내 비교한다.
    expected = getattr(request.app.state.settings, setting).get_secret_value()
    # 일반 문자열 비교 대신 상수 시간 비교 함수를 써서 비교 시간 차이를 줄인다.
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(403, 'Invalid API key')

# 관리자 라우터에 붙이는 인증 의존성이다. 상품 등록·수정 전에 검사한다.
def require_admin(request: Request, key: str | None = Security(header)):
    check(request, key, 'admin_api_key')

# 내부 라우터에 붙이는 인증 의존성이다. 주문 서비스 전용 키를 검사한다.
def require_internal(request: Request, key: str | None = Security(header)):
    check(request, key, 'internal_api_key')
