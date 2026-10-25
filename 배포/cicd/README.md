# CI/CD 도구 설치

GitLab·Jenkins·Argo CD를 Kubernetes에 Helm으로 설치하는 구성입니다. 각 도구는 독립된 모듈로 분리되어 필요한 도구만 개별적으로 설치할 수 있습니다.

## 구성

| 폴더 | 도구 역할 | 설치 구성 |
|---|---|---|
| `gitlab/` | 소스코드·배포 설정·컨테이너 이미지 관리 | 외부 PostgreSQL·Redis·Object Storage 연결, Gitaly 코드 저장용 기존 볼륨 연결 |
| `jenkins/` | 테스트·빌드 등 CI 작업 실행 | Controller·동적 Agent 구성, Jenkins 설정과 작업 이력 저장용 기존 볼륨 연결 |
| `argocd/` | Git 저장소의 배포 설정을 Kubernetes에 적용 | Argo CD 구성요소·내부 Redis 설치 |

각 모듈에는 Helm Chart·`values.yaml`·`README.md`가 포함되어 있습니다. 웹 접속은 모듈별 Envoy Gateway와 HTTPS로 제공합니다.

## 사용 방법

1. 설치할 도구 폴더의 `README.md`에서 필요한 외부 자원을 확인합니다.
2. 해당 폴더의 `values.yaml`에 볼륨·접속 정보 등 환경별 값을 입력합니다.
3. 해당 README의 Helm 명령으로 설치합니다.

**이 구성은 각 도구의 설치를 위한 것입니다.** GitLab Webhook·Jenkins Pipeline·Argo CD Application 등 도구 간 CI/CD 연동은 별도로 설정합니다.

