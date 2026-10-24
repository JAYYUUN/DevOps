# GitLab Cloud Native

GitLab을 Kubernetes에 Helm으로 배포하는 재사용 모듈입니다. PostgreSQL·Redis·Object Storage는 외부 서비스를 사용하고, 소스코드는 기존 클라우드 볼륨에 저장합니다.

## 구성요소

| 구성요소 | 역할 | 배치 |
|---|---|---|
| Webservice | 웹 화면·API 제공 | Kubernetes Pod |
| Sidekiq | 백그라운드 작업 처리 | Kubernetes Pod |
| GitLab Shell | Git 접근 요청 처리 | Kubernetes Pod |
| Gitaly | 소스코드·커밋·브랜치 저장 및 조회 | StatefulSet + 영구 볼륨 |
| Container Registry | 컨테이너 이미지 저장·조회 | Kubernetes Pod + 외부 Object Storage |
| Toolbox | 백업·복구·관리 작업 | Kubernetes Pod / 백업 CronJob |
| PostgreSQL | 사용자·프로젝트·권한·MR 정보 저장 | 외부 서비스 |
| Redis | 캐시·작업 큐·공유 상태 관리 | 외부 서비스 |
| Object Storage | 첨부파일·LFS·산출물·패키지·이미지·백업 저장 | 외부 서비스 |

공식 GitLab Chart 10.5.1(GitLab 19.5.1)을 하위 Chart로 사용합니다. PostgreSQL·Redis·MinIO는 설치하지 않습니다. Gitaly는 단일 인스턴스이며 자동 장애 전환 구성은 아닙니다.

## 필요한 외부 자원

| 자원 | 필요한 이유 |
|---|---|
| PostgreSQL DB·계정 | GitLab 서비스 정보를 저장하기 위해 필요 |
| 캐시용·영속 데이터용 Redis | 캐시와 작업 큐의 운영 정책을 분리하기 위해 필요 |
| Object Storage 버킷·접근 인증 | 파일·이미지·백업을 Pod 수명과 별개로 저장하기 위해 필요 |
| 기존 SSD 블록 볼륨·CSI 드라이버 | Gitaly Pod가 재생성되어도 코드와 이력을 유지하기 위해 필요 |
| Gitaly 전용 노드 | Git 작업의 자원 경합을 줄이고 cgroup 요구사항을 충족하기 위해 필요 |
| Ingress Controller·DNS·TLS 인증서 | 외부에서 GitLab과 Registry에 HTTPS로 접근하기 위해 필요 |
| Kubernetes Secret | 외부 서비스 인증정보를 GitLab에 전달하기 위해 필요 |

PostgreSQL 버전·확장 기능·계정 권한은 GitLab 요구사항에 맞춰 준비합니다. 기본 DB 이름은 gitlabhq_production입니다. Gitaly 노드는 Kubernetes 1.29 이상, containerd 2.1.0 이상, runc 1.1.9 이상, systemd 방식 cgroup v2와 필요한 cgroup 쓰기 권한을 확인해야 합니다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| Chart.yaml / Chart.lock | 공식 GitLab Chart 의존성과 버전 관리 |
| values.yaml | 환경별 설정 |
| templates/gitaly-pv.yaml | 기존 코드 저장용 볼륨의 PV 생성 |
| templates/validate.yaml | 필수 설정 검증 |
| templates/NOTES.txt | 설치 후 접속·조회 명령 안내 |
| charts/ | 공식 GitLab Chart 아카이브 |
| VALIDATION.md | 검증 범위와 적용 전 확인 사항 |

## 환경별 설정

values.yaml의 CHANGE_ME를 실제 값으로 변경합니다. CSP별 파일을 나누지 않고 같은 설정 항목을 사용합니다.

| 설정 | 입력할 값 |
|---|---|
| global.hosts.domain | GitLab·Registry의 기준 도메인 |
| global.ingress | 기존 Ingress provider·class·TLS Secret |
| global.psql | 외부 PostgreSQL 주소·포트·DB·계정·비밀번호 Secret |
| global.redis | 영속 데이터용 Redis 주소·TLS·인증 Secret |
| global.redis.cache | 캐시용 Redis 주소·TLS·인증 Secret |
| global.certificates.customCAs | 외부 서비스가 사설 CA를 사용하는 경우 CA Secret |
| global.appConfig | Object Storage 연결 Secret과 용도별 버킷 |
| global.registry.bucket | Registry 저장 버킷 |
| gitalyVolume | 기존 볼륨 ID·CSI 드라이버·파일시스템·접근 가능한 영역 |
| upstream.gitlab.gitaly.persistence | 코드 저장 용량·StorageClass·PV 선택 라벨 |
| upstream.gitlab.gitaly.nodeSelector | 전용 노드의 라벨. 기본 gitlab-gitaly: "true" |
| upstream.gitlab.gitaly.resources / cgroups | Gitaly 자원과 Git 프로세스 메모리 한도 |
| upstream.gitlab.webservice / sidekiq / gitlab-shell | 각 구성요소의 자원·replica |
| upstream.registry.storage | Registry용 Object Storage 설정 Secret |
| upstream.gitlab.toolbox.backups | 백업 연결 Secret·실행 주기 |

공식 Chart 설정은 upstream 아래에 지정합니다. global은 하위 Chart에도 전달됩니다.

### CSP에 따라 달라지는 값

| 항목 | AWS 일반 EBS CSI | NHN Cloud NKS |
|---|---|---|
| gitalyVolume.csi.driver | ebs.csi.aws.com | cinder.csi.openstack.org |
| gitalyVolume.csi.volumeHandle | EBS 볼륨 ID | Block Storage UUID |
| gitalyVolume.csi.fsType | 실제 볼륨 파일시스템 | 실제 볼륨 파일시스템 |
| gitalyVolume.nodeAffinity | 실제 노드 라벨·볼륨 AZ | 실제 노드 라벨·볼륨 AZ |

볼륨과 Pod가 실행될 노드는 연결 가능한 영역에 있어야 합니다. AWS EKS Auto Mode 등은 실제 사용 드라이버의 기존 볼륨 연결 절차를 확인합니다.

## 인증 Secret과 버킷

아래 Secret을 설치할 namespace에 준비합니다. 이름을 변경하면 values의 참조도 변경합니다. 비밀번호는 외부 서비스에 설정된 값과 일치해야 합니다.

| Secret 기본 이름 | 키 | 내용 |
|---|---|---|
| gitlab-external-postgresql | password | PostgreSQL 비밀번호 |
| gitlab-external-redis-persistent | password | 영속 Redis 비밀번호 |
| gitlab-external-redis-cache | password | 캐시 Redis 비밀번호 |
| gitlab-external-object-storage | connection | Rails용 Object Storage 연결 YAML |
| gitlab-external-registry-storage | config | Registry용 스토리지 설정 YAML |
| gitlab-external-backup-storage | config | Toolbox용 s3cmd 접속 설정 |
| gitlab-external-tls | tls.crt / tls.key | GitLab·Registry 도메인의 TLS 인증서·키 |
| gitlab-external-ca (선택) | ca.crt | 외부 서비스의 사설 CA |

Rails·Registry·백업은 연결 설정 형식이 서로 다릅니다. 각 형식은 아래 공식 Object Storage 문서를 따릅니다. 실제 인증값은 values나 Git 저장소에 넣지 않습니다. GitLab 내부 인증과 최초 root 비밀번호는 공식 Chart가 생성합니다.

기본 버킷: gitlab-lfs, gitlab-artifacts, gitlab-uploads, gitlab-packages, gitlab-registry, gitlab-backups, gitlab-backup-tmp. 용도별로 분리하고 Registry Secret의 bucket과 global.registry.bucket을 일치시킵니다.

## 설치

values와 외부 서비스·Secret·전용 노드를 준비한 뒤 실행합니다.

```bash
helm lint ./gitlab-cloud-native -f ./gitlab-cloud-native/values.yaml
helm template gitlab ./gitlab-cloud-native -n gitlab -f ./gitlab-cloud-native/values.yaml
helm upgrade --install gitlab ./gitlab-cloud-native \
  --kube-context YOUR_CONTEXT \
  --namespace gitlab --create-namespace \
  -f ./gitlab-cloud-native/values.yaml \
  --wait --wait-for-jobs --timeout 30m
```

접속 주소는 https://gitlab.DOMAIN, Registry는 https://registry.DOMAIN입니다. 기존 Ingress를 사용하며 Controller·DNS·TLS 발급은 이 모듈이 처리하지 않습니다. 기본 nginx 경로는 GitLab 10.x에서 비권장 전환 대상이므로 신규 라우팅을 구축한다면 공식 Gateway API 구성을 검토합니다. SSH clone의 외부 TCP 경로는 별도로 필요합니다.

```bash
kubectl get pods,pvc,ingress -n gitlab
kubectl get secret gitlab-gitlab-initial-root-password -n gitlab -o jsonpath='{.data.password}' | base64 -d
```

## 데이터 보존

Gitaly PVC는 StatefulSet이 생성합니다. release 이름이 gitlab이면 repo-data-gitlab-gitaly-0이며, 생성된 PV에 예약·바인딩됩니다. PV는 Retain/keep 정책을 사용합니다. 볼륨 유지가 백업이나 HA를 대신하지는 않습니다.

백업 CronJob 기본 주기는 `0 18 * * *`입니다. 컨트롤러 타임존과 원하는 보존 정책을 확인합니다. 외부 DB·Object Storage와 Rails 암호화 Secret도 복구 대상에 포함해야 합니다. 운영 적용 전 코드 push/clone, Pod 재생성 후 데이터 유지, 백업·복구를 확인합니다.

## 공식 문서

- [Cloud Native 참조 구조](https://docs.gitlab.com/administration/reference_architectures/cloud_native/)
- [Gitaly 실행 요건](https://docs.gitlab.com/administration/gitaly/kubernetes/)
- [외부 PostgreSQL](https://docs.gitlab.com/charts/advanced/external-db/)
- [외부 Redis](https://docs.gitlab.com/charts/advanced/external-redis/)
- [외부 Object Storage·Secret 형식](https://docs.gitlab.com/charts/advanced/external-object-storage/)
- [백업](https://docs.gitlab.com/charts/backup-restore/backup/)
