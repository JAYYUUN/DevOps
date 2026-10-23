# Scripts

Kubernetes Observability 환경의 배포 상태 확인 및 Helm 설정 백업을 위한 운영 스크립트입니다.

## 디렉터리 구조

```text
scripts/
├── verify.sh        # 배포 상태 확인
├── export-live.sh   # 현재 Helm 설정 백업
└── README.md
```

## 1. verify.sh

Prometheus, Loki, Fluentd의 배포 상태를 확인하는 스크립트입니다.

**주요 기능**
- Helm Release 상태 확인
- Kubernetes Pod 상태 확인
- Fluentd DaemonSet 배포 상태 확인
- Grafana 및 Loki Gateway 서비스 확인

**실행 방법**

프로젝트 루트 디렉터리에서 실행합니다.

```bash
bash ./scripts/verify.sh
```

## 2. export-live.sh

현재 Kubernetes 클러스터에 배포된 Helm Release의 설정값을 파일로 저장하는 스크립트입니다.

**주요 기능**
- `helm get values`를 이용한 설정값 추출
- Prometheus, Loki, Fluentd의 현재 적용 설정 백업
- 배포 설정 비교 및 복구를 위한 자료 확보

**실행 방법**

```bash
bash ./scripts/export-live.sh
```

## 사전 요구사항

- `kubectl`, `helm` CLI 설치
- Kubernetes 클러스터 접근 권한
- 대상 Helm Release가 클러스터에 배포되어 있어야 함

> 두 스크립트는 운영 편의 기능이며, Helm Wrapper Chart 배포에 필수는 아닙니다.
