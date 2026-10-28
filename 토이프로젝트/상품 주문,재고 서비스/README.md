# 상품 주문·재고 서비스

주문이 접수된 뒤 재고가 확보되고, 그 결과로 주문 상태가 바뀌는 흐름을 단계적으로 구현하는 프로젝트다.

## 현재 구현 범위

우선 완성할 사용자 흐름은 다음과 같다.

```text
주문 접수 → 재고 확보 요청 → 재고 확보 결과 → 주문 상태 변경
```

먼저 주문·재고 서비스 사이의 최소 흐름을 로컬에서 검증한다. 취소, 알림, 관리자 기능, Kubernetes 배포와 운영 기능은 이후 단계로 둔다.

첫 구현은 FastAPI 기반 HTTP API와 각 서비스별 SQLite 저장소를 사용한다. SQLite는 로컬 흐름을 빠르게 검증하기 위한 선택이며, Kafka와 운영 배포는 이후 단계다.

## 디렉터리

```text
.
├── services/
│   ├── order/       # 주문 접수와 재고 결과에 따른 주문 상태 변경
│   └── inventory/   # 재고 확보 요청 처리와 결과 생성
├── docs/
│   └── flows/       # 사용자·메시지 처리 흐름
└── deploy/           # 로컬 실행 구성이 필요해질 때 생성 (현재 없음)
```

주문 API와 재고 API를 별도 프로세스로 실행한다. 주문 서비스는 재고 서비스 응답을 받은 뒤 주문 상태를 확정하거나 거절한다. 재고 서비스 연결이 실패하면 실제 재고 상태를 알 수 없으므로 주문을 `pending`으로 남긴다.

## 로컬 실행

프로젝트 루트에서 개발 의존성을 설치한다.

```powershell
python -m pip install -r requirements-dev.txt
```

터미널 1에서 재고 서비스를 실행한다.

```powershell
python -m uvicorn inventory_service.main:app --app-dir services/inventory/src --port 8001
```

터미널 2에서 주문 서비스를 실행한다.

```powershell
python -m uvicorn order_service.main:app --app-dir services/order/src --port 8000
```

재고를 추가한 다음 주문을 접수한다.

```powershell
curl.exe -X POST http://127.0.0.1:8001/api/v1/inventory/widget/stock -H "Content-Type: application/json" -d '{"quantity":5}'
curl.exe -X POST http://127.0.0.1:8000/api/v1/orders -H "Content-Type: application/json" -d '{"product_id":"widget","quantity":2}'
```

테스트는 `python -m pytest`로 실행한다.

## 문서

- [서비스 디렉터리 안내](services/README.md)
- [주문 처리 흐름](docs/flows/order.md)

## 구현 원칙

- 먼저 주문에서 재고 결과 반영까지 하나의 흐름을 끝까지 동작시킨다.
- 첫 흐름에 필요하지 않은 서비스·실행 프로세스·배포 파일은 미리 만들지 않는다.
- 동작하는 흐름마다 테스트를 추가하고, 그다음 실패 처리·중복 처리·재시도·취소를 단계적으로 확장한다.
- 새 서비스나 공통 코드는 실제 요구가 생길 때 추가한다.
