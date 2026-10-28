# 상품 API

상품 등록·수정·조회와 주문용 상품 정보 제공을 담당한다.

> 현재는 문서와 파일 골격만 구성한 단계이다. Python 파일과 YAML은 실행 가능한 구현이 아니며 실제 배포할 수 없다.

MariaDB는 상품 원본, Redis는 상세 조회 캐시로 사용한다. 재고 수량은 재고 서비스가 관리한다. Kafka와 Outbox는 사용하지 않는다.

## 기능별 구현 문서

| 기능 | API | 문서 |
|---|---|---|
| 상품 등록 | `POST /api/v1/admin/products` | [상품 등록](docs/상품-등록.md) |
| 상품 수정 | `PATCH /api/v1/admin/products/{product_id}` | [상품 수정](docs/상품-수정.md) |
| 상품 목록 조회 | `GET /api/v1/products` | [상품 목록 조회](docs/상품-목록-조회.md) |
| 상품 상세 조회 | `GET /api/v1/products/{product_id}` | [상품 상세 조회](docs/상품-상세-조회.md) |
| 주문용 상품 조회 | `POST /internal/v1/products/lookup` | [주문용 상품 조회](docs/주문용-상품-조회.md) |
| 상태 확인 | `GET /health/live 및 GET /health/ready` | [상태 확인](docs/상태-확인.md) |

## 공통 구성

- [DB 구성](docs/DB-구성.md): 테이블·검증·마이그레이션
- [배포 설정](docs/배포-설정.md): 이미지·환경변수·공통 YAML

`src/`는 코드, `docs/`는 설명, `migrations/`는 DB 변경, `tests/`는 검증, `k8s/`는 배포 설정을 관리한다.

여러 Python 파일을 하나의 이미지에 포함하고 하나의 FastAPI 앱으로 실행한다. 기능별로 컨테이너를 나누지 않는다. 관리자 인증과 내부 서비스 인증은 구현 전에 결정한다.
