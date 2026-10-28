# 주문 서비스

[프로젝트 처음으로](../../README.md) · [서비스 목록](../README.md)

주문 서비스는 주문을 접수하고, 재고 서비스의 처리 결과에 따라 주문 상태를 변경한다. 첫 번째 목표는 [주문 처리 흐름](../../docs/flows/order.md)의 접수부터 주문 상태 변경까지를 실제로 연결하는 것이다.

## 첫 구현 범위

- 주문 요청을 받고 처리 중인 주문을 기록한다.
- 재고 확보 요청을 전달한다.
- 재고 확보 결과를 받아 주문 상태를 갱신한다.
- 정상 흐름을 확인하는 테스트를 작성한다.

취소, 인증·권한, 관리자 기능, 운영용 Kubernetes 설정은 첫 흐름에 필요해질 때까지 미룬다. 메시지 브로커, 데이터베이스, Outbox 등 구현 선택은 동작하는 최소 흐름에 필요한 만큼만 정한다.

## 디렉터리 원칙

주문 접수 API, 결과 처리 worker, 이벤트 발행기는 실행 역할이다. 필요하면 프로세스는 따로 실행하되 주문 서비스의 코드와 테스트는 이 디렉터리에서 관리한다.

## 실행

재고 서비스를 먼저 8001 포트에서 실행한 뒤 프로젝트 루트에서 다음 명령으로 주문 서비스를 실행한다.

```powershell
python -m uvicorn order_service.main:app --app-dir services/order/src --port 8000
```

주문은 `POST /api/v1/orders`에 `{"product_id":"widget","quantity":2}`를 보내 접수하고, `GET /api/v1/orders/{order_id}`로 상태를 조회한다. 재고 응답을 받을 수 없으면 주문은 `pending`으로 저장되고 HTTP 202를 반환한다.

기본 SQLite 파일은 `data/order.db`이며 `ORDER_DATABASE_PATH`로 변경할 수 있다. 재고 서비스 주소는 `INVENTORY_SERVICE_URL` 환경 변수로 설정한다.

프로젝트 루트에서 `python -m pytest`를 실행하면 주문·재고 연동 성공, 재고 부족, 재고 서비스 연결 장애 테스트를 수행한다.
