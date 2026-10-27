# 배포 모듈

[프로젝트 처음으로](../README.md)

배포 모듈마다 소스·Kubernetes YAML·설명 문서를 분리한다.

| 모듈 | Deployment 이름 | 사용하는 이미지 | 업무용 구성 |
|---|---|---|---|
| [상품 API](product-api/README.md) | `product-api` | `product-service` | Deployment + Service |
| [주문 API](order-api/README.md) | `order-api` | `order-service` | Deployment + Service |
| [주문 결과 처리](order-consumer/README.md) | `order-consumer` | `order-service` | Deployment |
| [주문 이벤트 발행](order-outbox/README.md) | `order-outbox` | `order-service` | Deployment |
| [재고 API](inventory-api/README.md) | `inventory-api` | `inventory-service` | Deployment + Service |
| [재고 이벤트 처리](inventory-consumer/README.md) | `inventory-consumer` | `inventory-service` | Deployment |
| [재고 결과 발행](inventory-outbox/README.md) | `inventory-outbox` | `inventory-service` | Deployment |
| [알림 API](notification-api/README.md) | `notification-api` | `notification-service` | Deployment + Service |
| [알림 이벤트 처리](notification-consumer/README.md) | `notification-consumer` | `notification-service` | Deployment |

## 공통 폴더 형태

```text
모듈명/
├── README.md
├── src/
│   └── .gitkeep
└── k8s/
    └── .gitkeep
```

`.gitkeep`은 빈 소스·YAML 폴더를 Git에서도 유지하기 위한 표시 파일이다. 구현 파일을 추가한 뒤 제거해도 된다.

## 이미지와 배포 모듈의 관계

모듈은 배포·실행 단위이며 이미지와 반드시 1:1이 아니다. 상품·주문·재고·알림 이미지 4개에 대해 실행 역할을 나눈다. 동일 서비스의 여러 모듈 소스를 같은 이미지에 포함하고 실행 명령을 다르게 하는 방향이다.

Dockerfile·빌드 범위·공통 코드 위치는 코드 구현 전에 정한다. 이번 폴더 분리만으로 각 모듈마다 서로 다른 이미지를 만들도록 변경한 것은 아니다.
