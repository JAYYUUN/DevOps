# GitLab · Jenkins · Argo CD 구성 위치 및 선택 기준

GitLab과 Jenkins는 VM 또는 Kubernetes에 설치할 수 있습니다.
설치 위치는 사용량만으로 결정하기보다 기존 운영 기반, 관리 방식, 장애 영향 범위를 고려하여 선택합니다.

Kubernetes에 설치하더라도 Pod 수를 늘리는 것만으로 이중화나 성능 확장이 보장되지는 않습니다.
구성요소별 다중 실행 지원 여부와 데이터 저장·복제·장애 전환 구성을 별도로 확인해야 합니다.

## 1. GitLab

GitLab은 소스 코드와 배포 설정을 저장하고 관리합니다.

### VM에 설치하는 경우

Linux 패키지로 설치하면 PostgreSQL, Redis, NGINX를 같은 VM에서 함께 구성하고 관리할 수 있습니다.

다음 상황에 적합합니다.

- Linux 패키지와 OS 서비스 기반의 운영 방식이 익숙한 경우
- GitLab 구성요소를 한 VM에서 통합 관리하려는 경우
- GitLab 운영을 위한 Kubernetes·영구 볼륨 등의 관리 부담을 줄이려는 경우
- 서비스용 Kubernetes와 GitLab의 장애·점검 영향을 분리하려는 경우

필요에 따라 VM 사양과 디스크 용량을 늘리거나 DB·Redis·저장소를 분리할 수 있습니다.
단일 VM 장애에 대비하여 데이터·설정·암호화 키를 외부에 백업하고 복구 절차를 준비해야 합니다.

### Kubernetes에 설치하는 경우

Helm Chart 등을 사용해 GitLab 구성요소를 Kubernetes에 배포합니다.

다음 상황에 적합합니다.

- Kubernetes와 영구 스토리지 운영 기반이 이미 갖춰진 경우
- Helm과 선언형 설정으로 배포·설정 관리 방식을 통일하려는 경우
- Pod 상태 감시·재시작·재배치 기능을 운영에 활용하려는 경우

운영 구성에서는 외부 PostgreSQL, Redis, Object Storage 등을 함께 설계해야 합니다.
Pod 재배치 가능 여부와 복구 시간은 스토리지 연결 방식, 노드 여유 자원 등에 영향을 받습니다.

GitLab의 이중화와 확장은 구성요소별 지원 방식에 따라 설계해야 하며,
데이터 손상이나 삭제에 대비한 백업도 별도로 필요합니다.

### 공식 설치 문서

- [GitLab Linux 패키지 설치](https://docs.gitlab.com/install/package/)
- [GitLab Helm Chart](https://docs.gitlab.com/charts/)

## 2. Jenkins

Jenkins는 빌드·테스트·컨테이너 이미지 생성·업로드 등의 작업을 실행합니다.

설계할 때는 Jenkins 본체와 실제 빌드 실행 환경을 구분합니다.

| 구성요소 | 역할 |
|---|---|
| Controller — Jenkins 본체 | 웹 화면, 작업 설정, 인증정보 관리 및 빌드 작업 배정 |
| Agent — 빌드 실행 담당 | 소스 다운로드, 빌드, 테스트, 이미지 생성·업로드 |

본체의 설치 위치와 Agent의 실행 위치는 독립적으로 선택할 수 있습니다.

### VM에 본체를 설치하는 경우

다음 상황에 적합합니다.

- OS 서비스 또는 VM 내 Docker로 Jenkins를 관리하려는 경우
- Jenkins 본체를 위한 Kubernetes·영구 볼륨 등의 관리 부담을 줄이려는 경우
- 서비스용 Kubernetes 장애 중에도 Jenkins 본체에 접근하려는 경우
- 기존 VM 백업·모니터링·복구 체계를 활용하려는 경우

Jenkins 설정과 인증정보 등이 저장되는 `JENKINS_HOME`을 백업해야 합니다.
본체 VM의 장애에 대비하려면 VM 복구 또는 HA 대책을 별도로 마련해야 합니다.

본체가 VM에 있어도 Agent는 별도 VM, Docker 컨테이너 또는 Kubernetes Pod로 구성할 수 있습니다.

### Kubernetes에 본체를 설치하는 경우

다음 상황에 적합합니다.

- Kubernetes 운영 기반과 영구 스토리지가 이미 갖춰진 경우
- Helm과 선언형 설정으로 Jenkins 배포·설정 관리를 통일하려는 경우
- Pod 상태 감시·재시작·재배치 기능을 활용하려는 경우

`JENKINS_HOME`을 영구 볼륨에 보관하고 별도로 백업해야 합니다.
노드 장애 후 재기동은 볼륨 연결 조건과 클러스터 가용 자원 등에 영향을 받습니다.

일반적인 Jenkins 구성은 본체 Pod 수를 늘려 같은 데이터를 공유하는 방식으로 이중화하지 않습니다.
빌드 처리량을 늘릴 때는 주로 Agent와 실행 자원을 확장합니다.

### 빌드 Agent의 실행 환경 선택

운영 환경에서는 빌드 작업을 Jenkins 본체와 분리하는 구성을 우선 검토합니다.

| 실행 환경 | 선택하는 상황 | 고려할 사항 |
|---|---|---|
| 별도 VM Agent | 고정된 도구·OS 환경, 전용 장비나 지속적인 작업 공간이 필요한 경우 | 빌드 도구 버전, 작업 파일 정리, VM 자원을 직접 관리 |
| Kubernetes Agent Pod | 작업별 실행 환경을 분리하고 필요할 때 생성·삭제하려는 경우 | Agent 이미지, 캐시·작업 공간, 권한, 클러스터 자원을 구성 |

Jenkins 본체를 VM에 두고 빌드 Agent만 Kubernetes Pod로 실행할 수도 있습니다.
이 경우 본체는 클러스터와 분리되지만, 해당 클러스터 장애 중에는 Pod 기반 빌드를 실행할 수 없습니다.

### 공식 설치 문서

- [Jenkins Linux 설치](https://www.jenkins.io/doc/book/installing/linux/)
- [Jenkins Kubernetes 설치](https://www.jenkins.io/doc/book/installing/kubernetes/)
- [Jenkins Agent](https://www.jenkins.io/doc/book/using/using-agents/)
- [Jenkins Kubernetes 플러그인](https://plugins.jenkins.io/kubernetes/)

## 3. Argo CD

Argo CD는 Kubernetes 안에서 실행되는 배포 관리 도구입니다.
Git에 저장된 배포 설정과 Kubernetes의 실제 상태를 비교하고,
자동 또는 수동 동기화로 원하는 상태를 반영합니다.

### Kubernetes에 구성하는 이유

- Kubernetes API를 통해 Deployment, Service 등의 리소스를 조회하고 변경합니다.
- Application, AppProject 등의 사용자 정의 리소스(CRD)로 배포 대상을 선언하고 관리합니다.
- ServiceAccount와 RBAC를 사용해 클러스터 접근 권한을 구성합니다.
- Argo CD 자체도 Kubernetes 리소스로 배포하여 상태 감시와 재시작 기능을 활용합니다.

### 설치할 클러스터 선택

| 설치 위치 | 선택하는 상황 | 고려할 사항 |
|---|---|---|
| 서비스용 클러스터 | 별도 관리용 클러스터 없이 운영 구성을 단순하게 유지하려는 경우 | 해당 클러스터 장애 시 Argo CD도 영향받음 |
| 별도 관리용 클러스터 | 여러 클러스터를 중앙 관리하거나 서비스 클러스터와 장애 영향을 분리하려는 경우 | 관리용 클러스터 운영과 대상 클러스터 접근 권한·네트워크 구성 필요 |

Argo CD는 자신이 설치된 클러스터뿐 아니라 별도로 등록한 외부 클러스터에도 배포할 수 있습니다.

Argo CD만 중단된 경우 이미 실행 중인 애플리케이션은 계속 동작할 수 있지만,
새로운 배포 동기화와 Git 기준의 상태 보정은 중단됩니다.

운영에 필요한 가용성 수준에 따라 Argo CD의 HA 구성을 검토하고,
배포 정의와 접근 자격정보 등 복구에 필요한 설정도 관리해야 합니다.

### 공식 설치 문서

- [Argo CD 설치 및 시작](https://argo-cd.readthedocs.io/en/stable/getting_started/)
- [Argo CD 설치 구성](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/)
