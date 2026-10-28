# 실행 환경 설정: DB·Redis 주소와 인증 키를 환경변수 또는 .env에서 읽는다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from functools import lru_cache
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 설정 항목과 검증 규칙을 한곳에 모은다. SecretStr는 설정 출력 시 비밀값을 가린다.
class Settings(BaseSettings):
    # 로컬에서는 .env도 읽는다. 이 앱과 관계없는 환경변수는 무시한다.
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    # DB 접속 URL은 필수다. 실제 접속할 때만 get_secret_value()로 값을 꺼낸다.
    database_url: SecretStr
    # Redis 주소와 캐시 유효 시간(초). TTL이 지나면 오래된 정보가 자동 삭제된다.
    redis_url: SecretStr = SecretStr('redis://localhost:6379/0')
    cache_ttl: int = Field(default=60, ge=1)
    # 관리자용 키와 서비스 간 호출용 키를 분리하고 최소 16자를 요구한다.
    admin_api_key: SecretStr = Field(min_length=16)
    internal_api_key: SecretStr = Field(min_length=16)

    # 설정 전체를 읽은 후 두 키가 같은지 검사해 권한 구분이 무너지는 것을 막는다.
    @model_validator(mode='after')
    def distinct_keys(self):
        if self.admin_api_key.get_secret_value() == self.internal_api_key.get_secret_value():
            raise ValueError('Admin and internal API keys must differ')
        return self

# 요청마다 .env를 다시 읽지 않고 최초에 검증한 설정을 재사용한다.
@lru_cache
def get_settings():
    return Settings()
