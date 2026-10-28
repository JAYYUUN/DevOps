# DB 마이그레이션

최초 버전은 [app/migrate.py](../src/app/migrate.py)가 products와 schema_migrations를 생성한다.

```bash
PYTHONPATH=src python -m app.migrate
```

DATABASE_URL과 인증 관련 환경변수가 필요하다. DB와 사용자는 먼저 준비한다. API 시작 시 자동 실행하지 않는다. 마이그레이션은 동시에 실행하지 않는다. 이 명령은 초기 생성 전용이며 기존 테이블의 구조 변경은 수행하지 않는다. 이후 변경은 버전별 마이그레이션 파일로 추가한다.
