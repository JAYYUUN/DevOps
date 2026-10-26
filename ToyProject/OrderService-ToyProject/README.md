# 주문서비스

Python 기반 주문·재고·알림 시스템을 AWS Kubernetes에서 운영하기 위한 설계 프로젝트입니다. 여기서 ‘주문서비스’는 프로젝트 전체의 이름이며, 개별 주문 API만을 뜻하지 않습니다.

**요구사항 → 논리 설계 → 배치·자원 설계 → 구성 요소별 구현 → 장애·복구 검증** 순서로 진행합니다. 현재 결과물은 설계 문서이며 애플리케이션과 인프라 코드는 포함하지 않습니다.

## 다시 시작할 때

1. [진행 현황](docs/progress/README.md)에서 현재 위치와 다음 작업을 확인합니다.
2. [요구사항](docs/requirements/README.md)을 읽고 범위와 미결 질문을 확인합니다.
3. 필요한 [논리 설계](docs/architecture/README.md)와 [결정 기록](docs/decisions/README.md)을 읽습니다.

## 문서 구조

```text
주문서비스/
├── README.md
└── docs/
    ├── README.md
    ├── requirements/
    │   └── README.md
    ├── architecture/
    │   └── README.md
    ├── decisions/
    │   └── README.md
    └── progress/
        └── README.md
```

| 문서 | 담당 내용 |
|---|---|
| [문서 안내](docs/README.md) | 문서 역할과 갱신 규칙 |
| [요구사항](docs/requirements/README.md) | 사용자·기능·첫 범위·완료 기준 |
| [논리 설계](docs/architecture/README.md) | 구성 요소의 책임·데이터 소유권·통신·실패 흐름 |
| [결정 기록](docs/decisions/README.md) | 선택지·근거·결정 이유·재검토 조건 |
| [진행 현황](docs/progress/README.md) | 현재 상태·미결 사항·다음 행동·재개 맥락 |

## 현재 출발 조건

| 항목 | 기준 |
|---|---|
| 서비스 주제 | 주문·재고·알림 시스템 |
| 언어 | Python |
| 환경 | AWS·Kubernetes, EKS 기준 검토 |
| 초기 Worker | 2대 |
| 관계형 DB | MariaDB 우선 검토 |
| 경험할 기술 | Redis·Kafka, 구체적인 역할은 요구사항과 연결해 확정 |
| 인프라 코드 방식 | Terraform 루트·차일드 모듈과 입력값 분리 |

세부 기능, 서비스 경계, 데이터 계층 배치, 가용성 목표는 검토 중입니다. 이전 Terraform ZIP은 재설계 전 초안이며 현재 설계의 확정 구현으로 취급하지 않습니다.

## 작업 원칙

- 한 번에 한 주제만 검토하고, 초안 제시 → 검토·수정 → 확정 → 구현 순서로 진행합니다.
- 제안·확정·보류·대체를 구분하며, 검증하지 않은 내용은 미검증으로 남깁니다.
- 공식 문서·기업 사례에서 확인한 내용과 프로젝트 자체 판단을 구분합니다.
- 각 주제는 담당 문서 한 곳에서 관리하고 다른 문서에서는 링크합니다.
- 상세 진행 상태는 progress 문서에서만 관리합니다.
- 작업을 마칠 때 다음 행동 하나와 갱신일을 기록합니다.
