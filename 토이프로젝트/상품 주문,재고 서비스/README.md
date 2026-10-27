# 상품 주문·재고 서비스 설계

## 1. 서비스별 구현 범위

| 서비스 | 구현할 기능 | 직접 관리할 데이터 |
|---|---|---|
| 상품 서비스 | 상품 등록·수정·판매 중지, 상품 목록·상세 조회, 조회 캐시 관리 | 상품명·설명·가격·판매 상태 |
| 주문 서비스 | 주문 접수, 주문 목록·상태 조회, 재고 처리 결과 반영, 주문 취소, 실패·미완료 주문 조회 | 주문·주문 상품·주문 상태 |
| 재고 서비스 | 입고 등록, 재고 조회, 주문 수량 예약, 예약 실패 처리, 취소 시 예약 해제 | 재고 수량·주문별 예약 내역 |
| 알림 서비스 | 주문 확정·실패·취소 이벤트 처리, 사용자 알림 목록·읽음 처리, 발송 실패 관리 | 사용자 알림·처리 상태 |

알림 기능의 첫 범위는 서비스 안에서 조회하는 알림을 저장하고 제공하는 것이다. 이메일·문자 전송은 이후 확장 대상으로 둔다. 초기 알림 실패 관리는 이벤트 처리와 알림 저장 실패의 확인·재시도를 의미한다.

## 서비스 구성도

```mermaid
flowchart TD
    CLIENT["사용자 · 관리자"]

    subgraph PRODUCT["상품 서비스"]
        PAPI["상품 API · Deployment + Service"]
        PDB[("상품 DB · MariaDB")]
        REDIS[("Redis · 상품 상세 캐시")]

        PAPI -->|"상품 등록·수정·조회"| PDB
        PAPI -->|"캐시 조회·저장·삭제"| REDIS
    end

    subgraph ORDER["주문 서비스"]
        OAPI["주문 API · Deployment + Service"]
        ORESULT["주문 결과 처리 · Deployment"]
        OPUBLISH["주문 이벤트 발행 · Deployment"]
        ODB[("주문 DB · 주문·처리 기록·Outbox")]

        OAPI -->|"주문·취소 접수 및 조회"| ODB
        ORESULT -->|"주문 상태·처리 기록·Outbox 저장"| ODB
        ODB -->|"발행 대기 Outbox 조회"| OPUBLISH
        OPUBLISH -->|"발행 완료·재시도 기록"| ODB
    end

    subgraph INVENTORY["재고 서비스"]
        IAPI["재고 API · Deployment + Service"]
        IWORKER["재고 이벤트 처리 · Deployment"]
        IPUBLISH["재고 결과 발행 · Deployment"]
        IDB[("재고 DB · 수량·예약·처리 기록·Outbox")]

        IAPI -->|"입고 등록·재고 조회"| IDB
        IWORKER -->|"예약·해제·처리 기록·Outbox 저장"| IDB
        IDB -->|"발행 대기 Outbox 조회"| IPUBLISH
        IPUBLISH -->|"발행 완료·재시도 기록"| IDB
    end

    subgraph NOTIFICATION["알림 서비스"]
        NAPI["알림 API · Deployment + Service"]
        NWORKER["알림 이벤트 처리 · Deployment"]
        NDB[("알림 DB · 알림·처리 기록")]

        NAPI -->|"알림 조회·읽음 처리"| NDB
        NWORKER -->|"알림·처리 기록 저장"| NDB
    end

    subgraph KAFKA["Kafka · 메시지 흐름별 토픽"]
        REQUEST["재고 확보·반환 요청"]
        RESULT["재고 확보·반환 결과"]
        FINAL["주문 확정·실패·취소 완료"]
    end

    CLIENT -->|"상품 조회·관리"| PAPI
    CLIENT -->|"주문 접수·조회·취소"| OAPI
    CLIENT -->|"재고 관리"| IAPI
    CLIENT -->|"알림 조회·읽음 처리"| NAPI

    OAPI -->|"HTTP · 원본 가격·판매 상태 확인"| PAPI

    OPUBLISH -->|"요청 발행"| REQUEST
    REQUEST -->|"요청 소비"| IWORKER

    IPUBLISH -->|"결과 발행"| RESULT
    RESULT -->|"결과 소비"| ORESULT

    OPUBLISH -->|"최종 결과 발행"| FINAL
    FINAL -->|"최종 결과 소비"| NWORKER
```

