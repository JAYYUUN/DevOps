# DB 구성

상태: 구현 완료

상품 서비스만 상품 DB에 접근한다. 다른 서비스는 API를 사용한다. 물리적인 전용 DB 서버를 확정하는 의미는 아니다.

## products 테이블

| 컬럼 | 자료형 | 설명 |
|---|---|---|
| id | BIGINT | 자동 증가 기본 키 |
| name | VARCHAR(200) | 공백 제거 후 1~200자, 필수 |
| description | TEXT | 선택 |
| price | DECIMAL(12,2) | KRW 원 단위 정수, 0~9,999,999,999 |
| status | VARCHAR(20) | ON_SALE 또는 STOPPED |
| created_at | DATETIME(6) | UTC 생성 시각 |
| updated_at | DATETIME(6) | UTC 수정 시각 |

가격·상태는 API 검증과 DB 제약조건을 함께 적용한다. status와 id의 복합 인덱스로 판매 중 목록 조회를 지원한다. 재고 수량은 저장하지 않는다.

## 파일 분담

- [models/product.py](../src/app/models/product.py): 테이블 매핑
- [database.py](../src/app/database.py): 연결·세션 관리
- [migrations](../migrations/README.md): 테이블 생성·변경 이력과 적용 방법

DB 생성은 API Pod 시작 때마다 수행하지 않는다. 마이그레이션 도구와 별도 실행 방식은 구현 단계에서 확정한다.
