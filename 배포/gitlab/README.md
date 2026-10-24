# GitLab

외부 PostgreSQL·Redis/Valkey·S3 호환 Object Storage를 연결하는 GitLab Helm 모듈입니다. 코드 저장에는 기존 SSD 볼륨을 사용합니다.

## 입력할 값

**values.yaml만 수정합니다.** 주소·계정·인증정보·기존 디스크처럼 외부 환경에서 정해지는 값만 입력합니다.

| 입력 | 넣을 값 |
|---|---|
| `global.hosts.domain` | 내부 기준 도메인. 예: company.internal |
| `global.ingress.class` | 기존 IngressClass 이름 |
| `global.psql.host`, `username` | 외부 PostgreSQL 주소·계정. 기본 계정 gitlab |
| `global.redis.host` | 외부 Redis/Valkey 주소. 캐시와 작업 큐 공용 |
| `secrets.postgresql.password` | 위 DB 계정 비밀번호 |
| `secrets.redisPersistent.password` | 위 Redis/Valkey 비밀번호. 한 번만 입력 |
| `secrets.objectStorage` | S3 endpoint·region·Access Key·Secret Key |
| `gitalyVolume.csi.driver` | AWS 일반 EBS: ebs.csi.aws.com / NHN: cinder.csi.openstack.org |
| `gitalyVolume.csi.volumeHandle` | 기존 SSD 볼륨 ID |
| `gitalyVolume.csi.fsType` | 실제 파일시스템. 기본 ext4 |
| `gitalyVolume.node` | 볼륨과 같은 AZ의 Gitaly 전용 노드 hostname 라벨 값 |
| `upstream.gitlab.gitaly.persistence.size` | 기존 디스크에 맞춘 용량. 기본 50Gi |

```bash
kubectl get ingressclass
kubectl get nodes -L kubernetes.io/hostname,topology.kubernetes.io/zone
```

DB 이름은 기본 gitlabhq_production, DB 포트는 5432, Redis 포트는 6379입니다. 다른 환경이면 values에 해당 항목을 추가해 덮어쓸 수 있습니다.

## 자동 처리

- DB·Redis·Object Storage Secret 생성과 연결.
- Redis/Valkey 하나를 캐시·작업 큐에 공통 연결.
- 자체 서명 HTTPS 인증서·개인키 생성과 GitLab·Registry 적용.
- 기존 Gitaly 디스크의 PV/PVC 연결·보존 정책과 노드 제한.
- Object Storage 기본 버킷 7개 생성. 이미 있으면 재사용하며 입력 키에 버킷 조회·생성·데이터 접근 권한이 필요합니다.
- 백업 CronJob과 기본 자원·replica 설정.

PostgreSQL·Redis/Valkey 서버, Object Storage 서비스·접근 키, 클라우드 디스크, Ingress Controller 자체는 만들지 않습니다. 기본 고정 설정은 Helm 라이브러리 하위 Chart가 자동 적용합니다.

## 설치

```bash
helm lint ./gitlab-cloud-native -f ./gitlab-cloud-native/values.yaml
helm upgrade --install gitlab ./gitlab-cloud-native \
  --namespace gitlab --create-namespace \
  -f ./gitlab-cloud-native/values.yaml \
  --wait --wait-for-jobs --timeout 30m
```

내부 DNS/hosts에서 gitlab.DOMAIN과 registry.DOMAIN을 Ingress 내부 IP로 연결합니다.

```bash
kubectl get pods,pvc,ingress -n gitlab
kubectl get secret gitlab-gitlab-initial-root-password -n gitlab -o jsonpath='{.data.password}' | base64 -d
```

접속: https://gitlab.DOMAIN / 계정: root.

## 확인 사항

- 인증값이 들어간 values는 Git에 올리지 않습니다. Helm release에도 저장됩니다.
- GitLab HTTPS는 자동이지만 PC·Git 클라이언트에는 생성된 CA 신뢰 등록이 필요합니다. 자동 갱신은 아닙니다.
- 외부 Redis는 기본 일반 TCP 연결입니다. TLS가 필요한 서비스는 `global.redis.scheme: rediss`를 추가합니다. DB는 TLS 인증서·호스트를 검증합니다. 사설 CA는 별도 신뢰 설정이 필요합니다.
- Gitaly는 지정 노드에서 실행하는 단일 인스턴스이며 자동 장애 전환이 아닙니다. 노드는 공식 런타임·cgroup 요건을 충족해야 합니다.
- Redis 공용 사용은 캐시와 큐의 자원·퇴출 정책에 영향을 주므로 운영 정책을 맞춥니다. 분리된 외부 서비스가 필요한 운영 환경은 고급 설정으로 분리합니다.
- 버킷이 사전 관리되면 `bucketSetup.enabled: false`를 추가해 자동 생성을 끌 수 있습니다.

[공식 구조](https://docs.gitlab.com/administration/reference_architectures/cloud_native/) · [Gitaly 요건](https://docs.gitlab.com/administration/gitaly/kubernetes/)
