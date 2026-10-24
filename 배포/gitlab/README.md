# GitLab Cloud Native

GitLab을 Kubernetes에 설치하고 외부 PostgreSQL·Redis·Object Storage와 연결하는 Helm 모듈입니다. 설정과 Secret 입력은 `values.yaml`에서 관리합니다.

## 구성

| 구성요소 | 역할·저장 위치 |
|---|---|
| Webservice·Sidekiq·GitLab Shell | 웹·API·백그라운드 작업·Git 요청 처리. Kubernetes Pod |
| Gitaly | 소스코드·커밋 저장. StatefulSet + 기존 클라우드 볼륨 |
| Registry | 컨테이너 이미지 제공. Pod + 외부 Object Storage |
| Toolbox | 백업·복구. Pod와 백업 CronJob |
| PostgreSQL | 사용자·프로젝트·권한 정보 저장. 외부 서비스 |
| Redis | 캐시·작업 큐 관리. 외부 캐시용/영속 데이터용 서비스 |
| Object Storage | 첨부파일·산출물·이미지·백업 저장. 외부 서비스 |

공식 GitLab Chart 10.5.1(GitLab 19.5.1)을 사용합니다. `templates/_tls-helpers.tpl`은 외부 Ingress에도 자동 생성된 인증서 Secret이 명시적으로 연결되도록 처리합니다. DB·Redis·MinIO는 설치하지 않습니다. Gitaly는 단일 인스턴스이며 자동 장애 전환 구성은 아닙니다.

## 준비할 자원

- **외부 PostgreSQL·Redis:** GitLab의 서비스 정보와 작업 큐를 저장하기 위해 필요합니다. 지원 버전·DB 확장 기능·접속 권한을 확인합니다.
- **외부 Object Storage와 버킷:** 첨부파일·이미지·백업을 보관합니다. 버킷은 용도별로 분리합니다.
- **기존 SSD 볼륨과 CSI 드라이버:** Gitaly Pod 재생성 시 코드와 이력을 유지합니다.
- **Gitaly 전용 노드:** 자원 경합을 줄입니다. 기본 라벨은 `gitlab-gitaly: "true"`입니다. 공식 cgroup·런타임 요건을 충족해야 합니다.
- **Ingress·DNS:** GitLab·Registry에 HTTPS로 접속하기 위해 필요합니다. Controller와 DNS는 별도 준비합니다. 인증서는 Chart가 자동 생성합니다.

## 설정 — values.yaml

| 항목 | 입력 내용 |
|---|---|
| `global.hosts`, `global.ingress` | 도메인·기존 IngressClass·자체 서명 TLS 설정 |
| `global.psql` | DB 주소·포트·계정·DB 이름 |
| `global.redis`, `global.redis.cache` | 영속/캐시 Redis 주소·포트·TLS 설정 |
| `global.appConfig`, `global.registry.bucket` | Object Storage 버킷 이름 |
| `gitalyVolume` | 기존 볼륨 ID·CSI 드라이버·파일시스템·영역 |
| `upstream.gitlab.gitaly` | 볼륨 용량·노드 배치·자원 |
| `upstream.gitlab` / `upstream.registry` | GitLab 구성요소의 자원·replica·백업 주기 |
| `secrets` | DB·Redis·Object Storage 인증값 |

`CHANGE_ME`를 실제 값으로 변경합니다. CSP별 파일은 없으며 같은 항목의 값만 바꿉니다.

| CSI 설정 | AWS 일반 EBS | NHN Cloud NKS |
|---|---|---|
| `driver` | `ebs.csi.aws.com` | `cinder.csi.openstack.org` |
| `volumeHandle` | EBS 볼륨 ID | Block Storage UUID |

파일시스템과 영역은 실제 볼륨·노드에 맞춥니다. PV 용량·클래스·selector는 Gitaly persistence 설정과 동일하게 적용됩니다.

## Secret 설정

인증값은 `values.yaml`의 `secrets`에 입력합니다. `templates/secrets.yaml`은 수정하지 않습니다. `create: true`이면 Helm이 Secret을 생성하고 GitLab이 참조합니다.

| 입력 위치 | 넣을 값 |
|---|---|
| `secrets.postgresql.password` | 외부 PostgreSQL의 `global.psql.username` 계정 비밀번호 |
| `secrets.redisPersistent.password` | `global.redis.host`에 연결할 Redis 비밀번호 |
| `secrets.redisCache.password` | `global.redis.cache.host`에 연결할 캐시 Redis 비밀번호 |
| `secrets.objectStorage.accessKey` | Object Storage에서 발급받은 S3 API Access Key |
| `secrets.objectStorage.secretKey` | 위 Access Key와 짝인 Secret Key |
| `secrets.objectStorage.region` | 해당 서비스에서 안내하는 S3 API 리전 값 |
| `secrets.objectStorage.endpoint` | `https://`로 시작하는 S3 API 주소. 개별 버킷 주소가 아님 |
| `secrets.objectStorage.pathStyle` | 경로에 버킷명을 넣는 방식이면 `true`. 서비스 요구사항에 맞춰 설정 |

```yaml
secrets:
  postgresql:
    create: true
    password: "외부_DB에_설정한_비밀번호"
  redisPersistent:
    create: true
    password: "영속_Redis_비밀번호"
  redisCache:
    create: true
    password: "캐시_Redis_비밀번호"
  objectStorage:
    create: true
    accessKey: "발급받은_Access_Key"
    secretKey: "발급받은_Secret_Key"
    region: "서비스에서_안내하는_S3_리전"
    endpoint: "https://서비스에서_안내하는_S3_endpoint"
    pathStyle: true
  customCA:
    create: false
    name: gitlab-external-ca
    certificate: ""
```

비밀번호는 외부 DB·Redis에 설정된 실제 값과 일치해야 합니다. Secret을 생성해도 외부 서비스의 비밀번호가 변경되지는 않습니다. Object Storage 입력값으로 Rails·Registry·백업용 Secret 3개를 생성합니다.

기존 Secret을 사용하려면 해당 `create`를 `false`로 변경하고 아래 위치에 기존 이름·키를 지정합니다.

| 용도 | 기존 Secret 참조 위치 |
|---|---|
| PostgreSQL | `global.psql.password.secret` / `key` |
| 영속 Redis | `global.redis.auth.secret` / `key` |
| 캐시 Redis | `global.redis.cache.password.secret` / `key` |
| Rails Object Storage | `global.appConfig.object_store.connection.secret` / `key` |
| Registry Object Storage | `upstream.registry.storage.secret` / `key` |
| 백업 Object Storage | `upstream.gitlab.toolbox.backups.objectStorage.config.secret` / `key` |

Object Storage의 `create` 설정은 세 연결 Secret에 함께 적용됩니다. Secret은 GitLab과 같은 namespace에 있어야 합니다.

사설 CA가 필요하면 `secrets.customCA.create: true`로 바꾸고 `certificate`에 CA PEM을 입력합니다. 아래 참조도 함께 추가합니다.

```yaml
global:
  certificates:
    customCAs:
      - secret: gitlab-external-ca
```

**실제 인증값이 들어간 values는 Git에 올리지 않습니다. 입력값은 Helm release 정보에도 저장됩니다.** GitLab 내부 인증과 최초 root 비밀번호는 공식 Chart가 생성합니다.

기본 버킷: `gitlab-lfs`, `gitlab-artifacts`, `gitlab-uploads`, `gitlab-packages`, `gitlab-registry`, `gitlab-backups`, `gitlab-backup-tmp`.

## HTTPS — 자체 서명 인증서 자동 생성

공식 GitLab Chart의 shared-secrets Job이 인증서와 개인키를 생성하고 Ingress에 적용합니다. 인증서 PEM·개인키 입력이나 cert-manager 설치는 필요하지 않습니다.

- `global.hosts.domain`: 내부 기준 도메인. 예: `company.internal`.
- `global.hosts.https: true`, `global.ingress.tls.enabled: true` 유지.
- `global.ingress.tls.secretName: ""` 유지. 기존 인증서를 지정하지 않아야 자동 생성됩니다.
- `global.ingress.configureCertmanager: false` 유지.

내부 DNS 또는 hosts에서 `gitlab.company.internal`, `registry.company.internal`을 Ingress 내부 IP로 연결합니다. 도메인을 바꿨다면 실제 주소도 맞춥니다.

release 이름이 gitlab일 때 생성되는 Secret:

| Secret | 내용 |
|---|---|
| `gitlab-wildcard-tls` | 인증서와 개인키 |
| `gitlab-wildcard-tls-ca` | PC·Git 클라이언트에 신뢰 등록할 CA 인증서 |
| `gitlab-wildcard-tls-chain` | 인증서 체인 |

CA 인증서를 내려받아 사용하는 PC·Git·컨테이너 도구의 신뢰 저장소에 등록합니다.

```bash
kubectl get secret gitlab-wildcard-tls-ca -n gitlab -o jsonpath='{.data.cfssl_ca}' | base64 -d > gitlab-ca.crt
```

외부 인증기관 접속 없이 생성됩니다. 브라우저 경고를 없애려면 CA 신뢰 등록이 필요하며, cert-manager 방식의 자동 갱신은 제공하지 않습니다. 외부 DB·Redis·Object Storage의 TLS/CA는 별개입니다.

## 설치

```bash
helm lint ./gitlab-cloud-native -f ./gitlab-cloud-native/values.yaml
helm upgrade --install gitlab ./gitlab-cloud-native \
  --kube-context YOUR_CONTEXT \
  --namespace gitlab --create-namespace \
  -f ./gitlab-cloud-native/values.yaml \
  --wait --wait-for-jobs --timeout 30m
```

```bash
kubectl get pods,pvc,ingress -n gitlab
kubectl get secret gitlab-gitlab-initial-root-password -n gitlab -o jsonpath='{.data.password}' | base64 -d
```

접속: `https://gitlab.DOMAIN`, 계정: `root`. TLS 인증서는 설정한 도메인을 기준으로 자동 생성합니다. SSH clone은 별도 TCP 공개가 필요합니다.

## 운영 확인

- Gitaly PV는 Retain/keep 정책을 사용합니다. PVC는 StatefulSet이 생성하며 기본 이름은 `repo-data-gitlab-gitaly-0`입니다.
- 코드 push/clone, Pod 재생성 후 데이터 유지, 백업·복구를 검증합니다. Rails 암호화 Secret과 외부 데이터도 별도로 보관합니다.
- Gitaly 노드의 Kubernetes·containerd·cgroup 요건과 서비스별 TLS·권한을 확인합니다. 자원 기본값은 환경에 맞게 조정합니다.
- 기본 nginx Ingress 경로는 GitLab 10.x에서 비권장 전환 대상이므로 신규 Controller를 구성한다면 Gateway API 방식을 먼저 검토합니다.

[공식 참조 구조](https://docs.gitlab.com/administration/reference_architectures/cloud_native/) · [Gitaly 실행 요건](https://docs.gitlab.com/administration/gitaly/kubernetes/) · [Object Storage](https://docs.gitlab.com/charts/advanced/external-object-storage/)
