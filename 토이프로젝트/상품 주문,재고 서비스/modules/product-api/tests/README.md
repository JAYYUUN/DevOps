# 테스트

```bash
pip install -r requirements-dev.txt
pytest -q
```

SQLite와 대체 캐시로 API·입력 검증·인증·캐시 삭제·내부 조회의 캐시 우회·Redis 실패 대체 동작을 검사한다. 실제 MariaDB 잠금·네트워크·Redis 서버 통합 테스트는 포함하지 않는다. Compose로 실제 서비스 실행 후 별도 확인한다.
