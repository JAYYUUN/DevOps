# 재고 서비스

[프로젝트 처음으로](../../README.md) · [서비스 목록](../README.md)

재고 서비스는 주문 서비스에서 전달한 확보 요청을 처리하고 성공 또는 실패 결과를 전달한다. 첫 번째 목표는 주문 접수부터 결과에 따른 주문 상태 변경까지의 흐름을 완성하는 것이다.

## 첫 구현 범위

- 주문의 재고 확보 요청을 받는다.
- 확보 가능 여부를 판단하고 결과를 주문 서비스에 전달한다.
- 요청이 중복 전달되어도 재고가 중복 반영되지 않도록 한다.
- 주문 서비스와 연결되는 정상 흐름 테스트를 작성한다.

입고 API, 예약 해제·주문 취소, 재시도 운영, Kubernetes 배포는 첫 흐름에 필요해질 때 추가한다. 구체적인 통신·저장 방식은 실제로 실행 가능한 최소 흐름을 구성하면서 결정한다.

## 디렉터리 원칙

재고 요청 처리 worker와 향후 재고 API는 하나의 재고 서비스 코드와 테스트를 공유한다. 요청을 처리하기 위한 API가 필요하지 않은 worker에 업무용 HTTP Service를 만들지 않는다.

## 실행

프로젝트 루트에서 개발 의존성을 설치한 뒤 실행한다.

```powershell
python -m pip install -r requirements-dev.txt
python -m uvicorn inventory_service.main:app --app-dir services/inventory/src --port 8001
```

`POST /api/v1/inventory/{product_id}/stock`으로 재고를 추가하고, `GET /api/v1/inventory/{product_id}`로 확인할 수 있다. 주문 서비스가 호출하는 재고 확보 경로는 `POST /internal/v1/reservations`이다.

현재는 첫 흐름을 작게 검증하기 위해 SQLite를 사용한다. 데이터베이스 파일은 기본적으로 `data/inventory.db`에 생성되며 `INVENTORY_DATABASE_PATH`로 변경할 수 있다.

내부 예약 API에는 아직 인증을 적용하지 않았으므로 로컬 개발용이다. 외부에 노출하거나 배포하기 전 서비스 간 인증·네트워크 접근 제한을 추가해야 한다.
