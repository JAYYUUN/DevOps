# GitLab

GitLab을 Kubernetes에 설치하고 외부 PostgreSQL·Redis/Valkey·Object Storage와 기존 코드 저장용 디스크에 연결합니다.

## 직접 입력할 값

**values.yaml의 CHANGE_ME만 변경합니다.** 외부 서비스를 만든 뒤 실제 주소·인증정보를 입력합니다.

| values.yaml 항목 | 무엇을 넣는가 | 어디서 확인하는가 / 예시 |
|---|---|---|
| `global.psql.host` | PostgreSQL 접속 주소. URL이 아닌 호스트명 또는 IP | 관리형 DB 상세의 접속 endpoint 또는 DB 서버 사설 IP. 예: `10.0.1.10` |
| `secrets.postgresql.password` | GitLab이 DB에 로그인할 비밀번호 | PostgreSQL에 만든 `gitlab` 계정의 비밀번호 |
| `global.redis.host` | Redis/Valkey 서버 주소 | 관리형 캐시 endpoint 또는 서버 사설 IP. 예: `10.0.1.20` |
| `secrets.redisPersistent.password` | 위 Redis/Valkey의 접속 비밀번호 | 해당 서비스 인증 토큰 또는 서버에 설정한 비밀번호. 캐시·작업 큐가 함께 사용 |
| `secrets.objectStorage.endpoint` | 파일을 저장할 S3 API 접속 URL | 클라우드 Object Storage의 S3 호환 API 안내. `https://` 포함, 버킷명 제외 |
| `secrets.objectStorage.region` | 해당 S3 API가 요구하는 리전 식별자 | 클라우드 Object Storage S3 API 문서. 콘솔의 한글 리전 이름이 아님 |
| `secrets.objectStorage.accessKey` | S3 API Access Key | 클라우드에서 발급한 S3 API 인증 키 |
| `secrets.objectStorage.secretKey` | 위 Access Key와 짝인 비밀 키 | Access Key 발급 시 함께 받은 Secret Key |
| `gitalyVolume.csi.driver` | Kubernetes가 클라우드 디스크를 연결할 때 쓰는 드라이버 이름 | AWS 일반 EBS: `ebs.csi.aws.com`, NHN NKS: `cinder.csi.openstack.org`. `kubectl get csidriver`로 설치 확인 |
| `gitalyVolume.csi.volumeHandle` | 미리 만든 코드 저장용 SSD 디스크의 ID | 클라우드 Block Storage/EBS 상세의 볼륨 ID. AWS는 `vol-...`, NHN은 UUID |
| `gitalyVolume.zone` | 위 디스크가 속한 가용 영역(AZ). 특정 노드 이름이 아님 | 클라우드 디스크 상세의 AZ 값. Kubernetes 노드의 `topology.kubernetes.io/zone` 라벨과 일치해야 함 |
| `upstream.gitlab.gitaly.persistence.size` | 코드 저장용으로 사용할 용량 | 기존 디스크 크기 이하. `50Gi`는 약 50GiB. 디스크를 생성·확장하는 값이 아님 |

기존 디스크의 영역은 Helm이 디스크 ID만으로 알 수 없어 입력이 필요합니다. **특정 Kubernetes 노드는 지정하지 않습니다.** 해당 영역의 노드 중에서 Kubernetes가 배치합니다. 영역 라벨이 다른 CSI 환경이라면 PV의 topology 설정을 그 드라이버에 맞춰야 합니다.

## 기본값으로 처리하는 설정

| 항목 | 기본 동작 |
|---|---|
| 접속 도메인 | `gitlab.internal`, `registry.internal` |
| IngressClass | 이름을 지정하지 않고 클러스터 기본 IngressClass 사용 |
| HTTPS | 인증서·개인키 자동 생성 및 적용 |
| Secret | 이름·키·생성·참조 자동 구성 |
| Redis/Valkey | 주소·비밀번호 한 번 입력, 캐시·작업 큐 공용 연결 |
| Gitaly 노드 | 볼륨의 영역 조건에 따라 자동 배치 |
| 파일시스템 | `ext4`. 디스크에 파일을 저장하는 형식이며 새 빈 디스크의 기본값 |
| 외부 DB | 계정 `gitlab`, DB `gitlabhq_production`, 포트 `5432` |
| 외부 Redis | 포트 `6379`, 일반 TCP 연결 |
| Object Storage 버킷 | 기본 버킷 조회·생성·재사용. 생성 권한 필요 |
| 백업·자원·replica | 기본 설정 자동 적용 |

기존 데이터가 있는 디스크라면 파일시스템을 확인해야 합니다. 예를 들어 XFS 디스크는 아래 값만 추가합니다. 파일시스템이 다른 디스크를 자동 변환하지 않습니다.

```yaml
gitalyVolume:
  csi:
    fsType: xfs
```

기본 도메인으로 접속하려면 내부 DNS 또는 PC hosts에서 두 이름을 Ingress 내부 IP로 연결합니다. DNS 등록은 이 Chart가 하지 않습니다. 자체 서명 CA는 PC·Git 클라이언트에 신뢰 등록해야 하며 자동 갱신 방식은 아닙니다.

## 필요한 경우에만 추가할 설정

클러스터에 기본 IngressClass가 없거나 다른 Controller를 선택할 때만 추가합니다. `nginx`는 예시이며 실제 IngressClass 이름을 사용합니다.

```yaml
global:
  ingress:
    class: nginx
```

```bash
kubectl get ingressclass
kubectl get nodes -L topology.kubernetes.io/zone
```

DB 계정·포트가 다르면 `global.psql.username`·`port`, Redis TLS가 필요하면 `global.redis.scheme: rediss`를 추가합니다. 외부 DB는 기본 TLS 인증서·호스트 검증을 사용하므로 사설 CA 서비스는 별도 CA 신뢰 설정이 필요합니다.

## 설치

외부 DB·Redis·Object Storage와 SSD 디스크, Ingress Controller는 먼저 준비합니다. Gitaly가 실행될 노드는 [공식 런타임·cgroup 요건](https://docs.gitlab.com/administration/gitaly/kubernetes/)을 충족해야 합니다.

```bash
helm lint ./gitlab -f ./gitlab/values.yaml

helm upgrade --install gitlab ./gitlab \
  --namespace gitlab --create-namespace \
  -f ./gitlab/values.yaml \
  --wait --wait-for-jobs --timeout 30m
```

```bash
kubectl get pods,pvc,ingress -n gitlab
kubectl get secret gitlab-gitlab-initial-root-password -n gitlab -o jsonpath='{.data.password}' | base64 -d
```

접속: `https://gitlab.internal`, 계정: `root`.

실제 비밀값이 들어간 values는 Git에 올리지 않습니다. Helm release에도 저장됩니다. 단일 Gitaly와 공용 Redis 구성은 자동 장애 전환·완전한 운영 HA를 의미하지 않습니다. 코드 유지·백업·복구는 실제 환경에서 검증해야 합니다.
