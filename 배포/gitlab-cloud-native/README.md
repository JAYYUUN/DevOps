# GitLab Cloud Native — 외부 데이터 서비스 연결형 Helm 구성

GitLab 공식 Cloud Native 참조 아키텍처의 **배치 방향**에 맞춘 GitLab 전용 Chart입니다. GitLab 웹·Sidekiq·Gitaly·Registry·Toolbox 등은 Kubernetes에서 실행하고, PostgreSQL·Redis·Object Storage는 이미 준비된 외부 서비스에 연결합니다.

공식 GitLab Chart 10.5.1 / GitLab 19.5.1을 수정 없이 하위 Chart로 포함합니다. 이 상위 Chart는 사용자 정의 구성으로, GitLab이 별도로 인증한 제품은 아닙니다. 자원·replica 기본값은 초기 구성 기준이며 공식 S/M/L/XL 용량 모델을 그대로 구현한 것은 아닙니다. 실제 부하와 복구 목표에 맞게 조정해야 합니다.

**설치 스크립트·config.env·CSP별 values 파일은 없습니다.** 설정은 values.yaml 하나에서 변경하고 Helm으로 실행합니다. 현재 파일은 기존 실습 패키지를 대체할 새로운 GitLab 구성입니다. 기존 설치를 자동 이관하거나 데이터·Secret을 복사하지 않습니다.

## 1. 구성과 범위

| 구성요소 | 이 Chart의 동작 | 데이터 저장 |
|---|---|---|
| GitLab 웹·Sidekiq·GitLab Shell | 공식 하위 Chart로 배포 | 외부 DB·Redis·Gitaly·Object Storage 사용 |
| Gitaly | 단일 StatefulSet 배포 | 기존 클라우드 볼륨을 가리키는 PV와 StatefulSet PVC |
| PostgreSQL | Pod/PVC 생성하지 않음 | 외부 PostgreSQL에서 관리 |
| Redis | Pod/PVC 생성하지 않음 | 외부 캐시용·영속 데이터용 Redis에서 관리 |
| 첨부파일·LFS·산출물·패키지 | 외부 Object Storage에 저장 | 용도별 외부 버킷 |
| Container Registry | Registry Pod 배포 | 외부 Object Storage 버킷 |
| MinIO | 설치하지 않음 | 외부 Object Storage 사용 |
| 백업 | Toolbox CronJob 활성화 | 별도 외부 백업 버킷 |

외부 서비스와 클라우드 디스크 자체를 만드는 Terraform/클라우드 API 코드는 포함하지 않습니다. Jenkins·Argo CD 연동도 이번 범위가 아닙니다.

Gitaly는 non-Cluster 단일 인스턴스입니다. replica 숫자를 늘려 Git 저장소 복제·자동 장애 전환이 구성되지 않습니다. 각 Git 저장소의 자동 장애 전환이 필요하면 VM의 Gitaly Cluster를 이용하는 Cloud Native Hybrid를 검토하세요.

## 2. 파일별 역할

| 파일/디렉터리 | 역할 | 변경할 때 |
|---|---|---|
| Chart.yaml | 상위 Chart와 공식 GitLab 의존 Chart의 버전 | 공식 Chart 업그레이드 시 |
| Chart.lock | 의존 Chart의 잠금 정보 | 의존 버전 변경 후 재생성 |
| values.yaml | 도메인, 외부 서비스, Secret 참조, 자원, Gitaly 볼륨 설정 | 환경별로 직접 변경 |
| templates/gitaly-pv.yaml | 기존 볼륨을 가리키는 공통 CSI PV | 일반적으로 변경하지 않음 |
| templates/validate.yaml | 미입력 값과 지원하지 않는 저장소 구조 차단 | 지원 구조 확장 시 |
| templates/NOTES.txt | Helm 설치 후 접속·확인 안내 | 안내 변경 시 |
| charts/gitlab-10.5.1.tgz | 수정하지 않은 공식 GitLab Chart | 버전 업그레이드 시 교체 |
| charts/SHA256SUMS | 포함 아카이브의 체크섬 | 아카이브 교체 시 갱신 |
| VALIDATION.md | 수행한 검증과 실제 환경에서 남은 검증 | 검증 결과 기록 |

하위 Chart를 `upstream`이라는 별칭으로 사용하므로, 공식 문서의 `gitlab.gitaly.persistence` 설정은 이 패키지에서는 `upstream.gitlab.gitaly.persistence`입니다. `global` 설정은 Helm의 전역 값으로 하위 Chart에도 전달됩니다.

## 3. 먼저 준비할 외부 자원

| 항목 | 준비 내용 |
|---|---|
| PostgreSQL | GitLab 버전에 맞는 PostgreSQL, DB·계정·확장 기능·백업·접속 허용 |
| Redis | 캐시용, 작업 큐·공유 상태용 엔드포인트와 인증. 관리형 HA라면 해당 서비스의 failover endpoint 사용 |
| Object Storage | S3 호환 연결 정보, 용도별 버킷, 접근 권한 |
| Gitaly 디스크 | 기존 SSD 블록 볼륨, ID·용량·파일시스템·연결 가능 AZ |
| 외부 접속 | DNS, 호환 Ingress Controller/IngressClass, TLS 인증서 |
| Kubernetes | Gitaly 실행 요건에 맞는 노드·런타임·cgroup과 전용 노드 배치 |

PostgreSQL은 MariaDB/MySQL로 대체할 수 없습니다. 해당 GitLab 버전의 시스템 요구사항과 관리형 서비스의 확장 기능·권한 제한을 확인하세요. DB는 기본 gitlabhq_production이며, GitLab 계정에 필요한 DB 권한을 부여합니다. superuser를 주지 않는다면 공식 문서의 amcheck·pg_trgm·btree_gist 확장 기능을 사전 준비합니다. DB 초기 테이블·마이그레이션은 공식 Chart의 migrations Job이 담당합니다.

Redis 캐시와 영속 용도는 분리했습니다. global.redis.host는 큐·공유 상태 등 기본 연결이고 global.redis.cache.host만 별도 캐시 서버를 가리킵니다. 동일 서버를 쓰려면 메모리·퇴출 정책·복구 영향을 검토한 뒤 주소/Secret을 맞춰야 하며, 이는 이 기본 분리 구조와 다릅니다. Redis Cluster나 Sentinel은 단순 호스트 대체만으로 연결되지 않을 수 있으므로 GitLab 지원 방식에 맞춰 설정하세요.

### Gitaly 노드 요구사항

작성 시 확인한 공식 Gitaly on Kubernetes 문서는 Kubernetes 1.29 이상, runc 1.1.9 이상, cgroup v2와 systemd cgroup 구조, containerd 2.1.0 이상 및 cgroup 쓰기 설정 등을 요구합니다. Pod의 /sys/fs/cgroup 접근과 root init container 허용도 필요합니다. 관리형 Kubernetes라면 제공 런타임이 이 요구를 만족하는지 설치 전에 확인해야 합니다.

이 Chart는 Gitaly cgroups를 활성화하고 `gitlab-gitaly: "true"` 라벨이 있는 노드로 배치합니다. 라벨을 붙이는 것만으로 노드가 전용화되거나 런타임 설정이 바뀌지는 않습니다. 전용 노드 풀·taint/toleration·여유 자원도 환경에 맞게 구성하세요. 기본 요청/상한은 2 CPU·8Gi이고 cgroup 메모리는 7Gi이므로 실제 노드와 부하에 맞게 함께 조정합니다.

```bash
kubectl version
kubectl get nodes -o wide
kubectl get csidriver
kubectl get ingressclass
kubectl get nodes -L topology.kubernetes.io/zone
```

전용 노드를 선택하고 실제 이름으로 실행합니다.

```bash
kubectl label node YOUR_GITALY_NODE gitlab-gitaly=true
```

노드 런타임 변경·재시작은 이 패키지가 수행하지 않습니다. 기존 노드에 영향이 있으므로 공식 가이드와 해당 CSP 지원 정책에 맞춰 별도 진행하세요.

## 4. values.yaml에서 커스터마이징할 부분

| 경로 | 설정할 내용 |
|---|---|
| global.hosts.domain | gitlab.DOMAIN, registry.DOMAIN의 기준 도메인 |
| global.ingress.class | 이미 설치된 IngressClass 이름 |
| global.ingress.provider | 실제 컨트롤러와 GitLab Chart가 지원하는 provider |
| global.ingress.tls.secretName | GitLab·Registry 도메인을 포함하는 TLS Secret |
| global.psql | 외부 DB 호스트·포트·사용자·DB·비밀번호 Secret |
| global.extraEnv.PGSSLMODE | 기본 verify-full. DB 서버 인증서와 호스트 검증 |
| global.extraEnv.PGSSLROOTCERT | libpq가 사용할 CA bundle 경로 |
| global.certificates.customCAs | 사설 CA 사용 시 추가 CA Secret |
| global.redis | 영속 Redis 호스트·포트·TLS·인증 |
| global.redis.cache | 캐시 Redis 호스트·포트·TLS·인증 |
| global.appConfig.object_store.connection | Rails Object Storage 연결 Secret |
| global.appConfig.*.bucket | 첨부파일·LFS·산출물·패키지·백업 버킷 |
| global.registry.bucket | Registry 버킷. Registry Secret의 버킷과 일치해야 함 |
| gitalyVolume | 기존 코드 저장용 볼륨의 드라이버·ID·파일시스템·영역 |
| upstream.gitlab.gitaly.persistence | Gitaly 볼륨 용량·StorageClass·PV selector |
| upstream.gitlab.gitaly.resources/cgroups | Gitaly Pod 자원과 Git 프로세스 cgroup 한도 |
| upstream.gitlab.gitaly.nodeSelector | 실제 준비한 전용 노드 라벨 |
| upstream.gitlab.webservice/sidekiq/gitlab-shell | replica·resources·스케줄링 등 공식 Chart 옵션 |
| upstream.registry | Registry replica·Object Storage Secret 등 |
| upstream.gitlab.toolbox.backups | 백업 Secret·주기·백업 작업 옵션 |

CHANGE_ME는 실제 값으로 바꿔야 lint/template/install이 진행됩니다. values에 실제 비밀번호나 S3 Secret Key를 저장하지 않고 기존 Kubernetes Secret을 참조합니다.

### CSP별로 달라지는 값 — 파일 분리 없이 같은 항목 수정

| 항목 | AWS 일반 EBS CSI | NHN Cloud NKS Cinder CSI |
|---|---|---|
| gitalyVolume.csi.driver | ebs.csi.aws.com | cinder.csi.openstack.org |
| gitalyVolume.csi.volumeHandle | vol-... 형식의 EBS ID | Block Storage UUID |
| nodeAffinity | 실제 EBS AZ와 노드 topology | 실제 Block Storage AZ와 노드 topology |
| fsType | 기존 볼륨의 실제 파일시스템 | 기존 볼륨의 실제 파일시스템 |
| S3 연결 endpoint·region | 사용 리전과 S3 연결 방식 | NHN Object Storage S3 호환 endpoint·region |

파일시스템은 CSP만 보고 고정하지 마세요. 기존 데이터 볼륨의 실제 형식을 확인해야 합니다. AWS EKS Auto Mode 등은 일반 EBS CSI와 기존 볼륨 처리 방식이 다를 수 있습니다. 실제 클러스터 드라이버를 기준으로 확인하세요. 영역 라벨은 예시의 topology.kubernetes.io/zone을 그대로 가정하지 말고 실제 라벨과 맞춥니다.

템플릿은 Gitaly persistence의 용량·접근 모드·클래스·selector 값을 읽어 PV에도 동일하게 적용합니다. 같은 값을 중복 수정하지 않습니다. `storageClass: "-"`를 쓰면 PV·PVC 모두 클래스 없음으로 명시합니다. 기본 gitlab-static은 정적 바인딩용 이름이며 이 Chart는 StorageClass 객체를 생성하지 않습니다.

## 5. 외부 인증 Secret 준비

모든 Secret은 GitLab을 설치할 namespace 안에 있어야 합니다. 아래는 기본 이름·키입니다. 조직의 Secret Manager/External Secrets 등으로 준비해도 됩니다.

| Secret | 키 | 내용 |
|---|---|---|
| gitlab-external-postgresql | password | 실제 외부 DB 계정 비밀번호 |
| gitlab-external-redis-persistent | password | 실제 영속 Redis 비밀번호 |
| gitlab-external-redis-cache | password | 실제 캐시 Redis 비밀번호 |
| gitlab-external-object-storage | connection | Rails용 S3 연결 YAML |
| gitlab-external-registry-storage | config | Registry 스토리지 설정 YAML |
| gitlab-external-backup-storage | config | Toolbox용 s3cmd 설정(.s3cfg) |
| gitlab-external-tls | tls.crt, tls.key | GitLab·Registry 도메인을 포함하는 인증서·키 |
| gitlab-external-ca (선택) | ca.crt | 사설 DB/Redis/Object Storage CA. customCAs에 참조 추가 |

이 Chart는 외부 DB/Redis 계정 비밀번호를 임의 생성하지 않습니다. 실제 서버에 설정된 인증과 일치해야 하기 때문입니다. GitLab 내부 통신용 Secret과 최초 root 비밀번호는 공식 Chart의 shared-secrets Job이 생성합니다.

namespace를 먼저 준비합니다.

```bash
kubectl create namespace gitlab --dry-run=client -o yaml | kubectl apply -f -
```

권한 제한된 로컬 파일로 실제 비밀번호/연결 정보를 준비했다면 다음과 같이 생성할 수 있습니다. 비밀번호 파일은 불필요한 마지막 줄바꿈이 없도록 작성하고 secrets/는 Git에 올리지 마세요.

```bash
kubectl create secret generic gitlab-external-postgresql -n gitlab --from-file=password=secrets/postgresql-password
kubectl create secret generic gitlab-external-redis-persistent -n gitlab --from-file=password=secrets/redis-persistent-password
kubectl create secret generic gitlab-external-redis-cache -n gitlab --from-file=password=secrets/redis-cache-password
kubectl create secret generic gitlab-external-object-storage -n gitlab --from-file=connection=secrets/object-storage.yaml
kubectl create secret generic gitlab-external-registry-storage -n gitlab --from-file=config=secrets/registry-storage.yaml
kubectl create secret generic gitlab-external-backup-storage -n gitlab --from-file=config=secrets/backup.s3cfg
kubectl create secret tls gitlab-external-tls -n gitlab --cert=secrets/tls.crt --key=secrets/tls.key
```

위 secrets/ 경로는 설명용이며 실제 인증 파일은 배포하지 않습니다.

### Rails Object Storage 연결 — object-storage.yaml 내용

```yaml
provider: AWS
region: YOUR_REGION
aws_access_key_id: YOUR_ACCESS_KEY
aws_secret_access_key: YOUR_SECRET_KEY
endpoint: https://YOUR_S3_COMPATIBLE_ENDPOINT
path_style: true
```

S3 호환 서비스의 일반 예시입니다. provider 이름은 연결 프로토콜을 의미하므로 S3 호환 NHN 서비스도 대응하는 AWS 연결 형식을 사용합니다. endpoint·region·path_style은 실제 서비스에 맞춥니다. AWS IAM 인증을 사용한다면 고정 키 대신 공식 IRSA/Workload Identity 설정과 Pod ServiceAccount 권한을 별도로 구성합니다. Secret 내용은 같은 이름으로 교체할 수 있으며 CSP별 설치 파일을 만들 필요가 없습니다.

### Registry 저장소 — registry-storage.yaml 내용

```yaml
s3:
  accesskey: YOUR_ACCESS_KEY
  secretkey: YOUR_SECRET_KEY
  bucket: gitlab-registry
  region: YOUR_REGION
  regionendpoint: https://YOUR_S3_COMPATIBLE_ENDPOINT
  secure: true
  v4auth: true
  pathstyle: true
redirect:
  disable: true
```

Registry와 Rails의 저장소 설정 형식은 다릅니다. 드라이버·옵션은 Registry 버전과 S3 호환 서비스에 맞춰 확인하세요. 체크섬·multipart upload 등 호환성에 문제가 있다면 공식 s3_v2 드라이버 설정을 포함해 실환경에서 검증해야 합니다. 실제 클라우드 연결은 아직 검증하지 않았습니다.

### 백업 연결 — backup.s3cfg 내용

```ini
[default]
access_key = YOUR_ACCESS_KEY
secret_key = YOUR_SECRET_KEY
host_base = YOUR_S3_COMPATIBLE_HOST
host_bucket = YOUR_S3_COMPATIBLE_HOST
use_https = True
bucket_location = YOUR_REGION
signature_v2 = False
```

host_base는 https://를 제외한 호스트명입니다. 이 예시는 path-style S3 호환 연결을 가정합니다. AWS virtual-hosted-style 등을 사용한다면 host_bucket 등도 서비스 요구사항에 맞게 수정하세요. 백업에 필요한 버킷 읽기·쓰기 권한을 확인합니다.

## 6. 외부 Object Storage 버킷

기본 활성 용도에 대해 다음 버킷을 외부 서비스에서 준비합니다. 용도마다 별도 버킷을 사용합니다.

- gitlab-lfs
- gitlab-artifacts
- gitlab-uploads
- gitlab-packages
- gitlab-registry
- gitlab-backups
- gitlab-backup-tmp

이름은 values에서 바꿀 수 있습니다. Registry는 Secret 내부와 global.registry.bucket이 일치해야 합니다. 백업 권한·보존 기간·복제 대상은 운영 데이터와 구분해 설계합니다. DB·Redis·스토리지 관리 권한 전체를 전달하는 대신 필요한 연결 권한을 사용합니다.

## 7. Helm으로 설치

이 README가 있는 gitlab-cloud-native 폴더에서 values.yaml을 수정합니다.

```bash
helm lint . -f values.yaml
helm template gitlab . --namespace gitlab -f values.yaml
```

대상 context, 외부 주소, Gitaly 볼륨 ID, Secret을 확인하고 설치합니다.

```bash
helm upgrade --install gitlab . \
  --kube-context YOUR_CONTEXT \
  --namespace gitlab --create-namespace \
  -f values.yaml \
  --wait --wait-for-jobs --timeout 30m
```

YOUR_CONTEXT를 실제 값으로 바꾸세요. 미입력 상태에서는 실행되지 않습니다. 이 명령이 외부 DB·버킷을 생성하지는 않습니다. Chart 아카이브는 포함하지만 노드가 컨테이너 이미지를 다운로드할 수 있어야 합니다.

접속은 기존 Ingress로 제공합니다. Ingress Controller·LoadBalancer와 DNS는 별도 준비합니다. 기본값은 외부 nginx 계열 Ingress를 가정합니다. **GitLab 10.x에서는 Gateway API가 기본 경로이며 NGINX Ingress는 비권장 전환 대상이므로**, 기존 컨트롤러가 없는 신규 환경에서는 Gateway API 경로부터 검토하세요. 이 패키지는 Controller/Gateway를 설치하지 않습니다. 호환되는 기존 provider/class로 변경할 수 있으며 실제 컨트롤러별 TLS·Registry 업로드 동작을 확인해야 합니다.

SSH clone용 TCP 경로는 HTTP Ingress만으로 열리지 않습니다. 처음에는 HTTPS clone/push로 테스트합니다.

수정 후 같은 Helm 명령으로 업데이트합니다. Gitaly 볼륨 ID·PV 이름·StorageClass 변경은 데이터 이관 명령이 아닙니다. 기존 GitLab 설치가 있다면 이 Chart를 그대로 덮어쓰지 말고 DB·Redis·코드·Secret 이관 절차를 따로 준비하세요.

## 8. 상태와 로그인 확인

```bash
helm status gitlab -n gitlab
kubectl get pods,pvc,ingress -n gitlab
kubectl get pv gitlab-gitaly-existing
kubectl get events -n gitlab --sort-by=.lastTimestamp
```

release 이름이 gitlab이면 Gitaly PVC는 `repo-data-gitlab-gitaly-0`입니다. PV의 claimRef로 해당 PVC에 예약하고, PVC의 selector·클래스·용량으로 이 PV와 바인딩합니다. 임의의 기존 PVC 이름을 받는 existingClaim 방식은 아닙니다. PV 이름·namespace를 바꾸면 확인 명령도 맞춥니다.

최초 root 비밀번호:

```bash
kubectl get secret gitlab-gitlab-initial-root-password -n gitlab -o jsonpath='{.data.password}' | base64 -d
```

`https://gitlab.DOMAIN`에 root로 접속합니다. 초기 Secret은 계정 비밀번호를 변경한 이후 현재 값과 다를 수 있습니다.

## 9. 코드 유지·백업 테스트

1. UI에서 테스트 프로젝트를 만들고 HTTPS로 clone합니다.
2. 테스트 코드를 commit/push하고 UI에서 코드·커밋·프로젝트 정보를 확인합니다.
3. Gitaly Pod 이름을 확인한 뒤 해당 Pod만 재생성합니다. 단일 Gitaly이므로 시험 중 Git 작업은 일시 중단될 수 있습니다.
4. 기존 PVC/PV가 다시 연결되었는지, 코드·이력·프로젝트 정보가 유지되고 다시 clone되는지 확인합니다.
5. Toolbox 백업을 수동 실행하고 백업 버킷에 파일이 생성되는지 확인합니다.
6. 운영 적용 전 별도 검증 환경에서 DB·Git·Object Storage·Secret을 포함한 복구를 확인합니다.

```bash
kubectl get pods -n gitlab -l app=gitaly
kubectl delete pod gitlab-gitaly-0 -n gitlab
kubectl rollout status statefulset/gitlab-gitaly -n gitlab --timeout=10m
kubectl get pvc repo-data-gitlab-gitaly-0 -n gitlab -o wide
kubectl create job gitlab-backup-test --from=cronjob/gitlab-toolbox-backup -n gitlab
kubectl logs -f job/gitlab-backup-test -n gitlab
```

release 이름 gitlab 기준 첫 시험용 명령입니다. 같은 이름의 백업 Job이 있다면 다른 시험 이름을 쓰세요. DB 데이터 손상이나 볼륨 삭제를 이용하는 시험은 하지 않습니다.

백업 기본 주기 `0 18 * * *`는 컨트롤러 타임존에 따르므로 기대 실행 시각을 확인하고 변경하세요. 외부 PostgreSQL의 PITR·백업, Redis 복구, Object Storage 버전 관리·복제도 별도로 설계합니다. GitLab 백업이 모든 외부 데이터와 Secret을 자동 포함한다고 가정하지 말고 선택한 방식의 백업 대상을 확인해야 합니다.

**Rails 암호화 Secret은 별도 보관해야 합니다.** 기본 백업에 포함되지 않으며, DB만 복구하면 암호화된 정보를 읽지 못할 수 있습니다. Secret·인증서·연결 정보도 보호된 보관소에서 관리합니다.

## 10. Gitaly 볼륨 유지 정책

PV는 Retain, Helm resource-policy는 keep입니다. PVC는 StatefulSet 기본 유지 동작에 따르며, 이 Chart는 Pod 교체나 Helm 삭제 시 PVC 자동 삭제 정책을 추가하지 않습니다. 클라우드에서 볼륨을 직접 삭제하는 것을 막는 설정은 아닙니다.

Helm 삭제 후 PV/PVC가 남을 수 있습니다. 재설치 시 claimRef·PVC 상태·소유권·기존 데이터를 확인해야 하며, 삭제해서 해결하지 마세요. Retain은 HA나 백업을 대신하지 않습니다. 코드 저장의 내구성과 Git 작업의 지속 가용성은 별개입니다.

## 11. 공식 문서와 적용 한계

- Cloud Native: https://docs.gitlab.com/administration/reference_architectures/cloud_native/
- Gitaly on Kubernetes: https://docs.gitlab.com/administration/gitaly/kubernetes/
- External PostgreSQL: https://docs.gitlab.com/charts/advanced/external-db/
- External Redis: https://docs.gitlab.com/charts/advanced/external-redis/
- External Object Storage: https://docs.gitlab.com/charts/advanced/external-object-storage/
- Storage: https://docs.gitlab.com/charts/installation/storage/
- Backup: https://docs.gitlab.com/charts/backup-restore/backup/

외부 서비스 실접속, Gitaly 노드 요건, 마운트·쓰기·복구, 실제 부하·HA는 미검증입니다. 공식 Chart 업데이트 시 설정·요구사항 호환성을 다시 확인해야 합니다. Helm의 정적 렌더링 검증은 운영 환경 검증을 대신하지 않습니다.
