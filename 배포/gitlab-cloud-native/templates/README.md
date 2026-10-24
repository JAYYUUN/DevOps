# GitLab 템플릿 설정

**값은 모두 `values.yaml`에 입력합니다.** `templates/`의 YAML은 입력값으로 리소스를 생성하므로 직접 수정하지 않습니다.

## secrets.yaml — 인증정보 생성

| values.yaml 위치 | 넣을 값 |
|---|---|
| `secrets.postgresql.password` | `global.psql.username`에 지정한 외부 PostgreSQL 계정의 실제 비밀번호 |
| `secrets.redisPersistent.password` | `global.redis.host`에 연결할 Redis의 실제 비밀번호 |
| `secrets.redisCache.password` | `global.redis.cache.host`에 연결할 캐시 Redis의 실제 비밀번호 |
| `secrets.objectStorage.accessKey` | Object Storage의 S3 API Access Key |
| `secrets.objectStorage.secretKey` | 위 Access Key와 함께 발급된 Secret Key |
| `secrets.objectStorage.region` | 해당 Object Storage의 S3 API 리전 값 |
| `secrets.objectStorage.endpoint` | `https://`로 시작하는 S3 API 주소. 버킷 주소가 아님 |
| `secrets.objectStorage.pathStyle` | S3 서비스가 요구하는 경로 방식. 경로에 버킷명을 넣으면 `true` |
| `secrets.tls.certificate` | GitLab·Registry 도메인의 인증서 PEM 전문 |
| `secrets.tls.privateKey` | 위 인증서와 짝인 개인키 PEM 전문 |

입력 예시:

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
  tls:
    create: true
    certificate: |-
      -----BEGIN CERTIFICATE-----
      실제 인증서 내용
      -----END CERTIFICATE-----
    privateKey: |-
      -----BEGIN PRIVATE KEY-----
      실제 개인키 내용
      -----END PRIVATE KEY-----
```

`create: true`이면 Helm이 Secret을 생성합니다. 이름과 키는 `global`·`upstream`에 지정된 참조를 사용하므로 기본값은 그대로 두면 됩니다. `create: false`이면 해당 이름·키의 기존 Secret을 사용합니다. Object Storage 설정 하나로 Rails·Registry·백업 연결 Secret 3개를 생성합니다.

사설 CA가 필요하면 `secrets.customCA.create: true`와 `certificate`에 CA PEM을 넣고, `global.certificates.customCAs`에 같은 Secret 이름을 등록합니다.

실제 인증값이 들어간 values는 Git에 올리지 않습니다. Helm release에도 입력값이 저장됩니다.

## gitaly-pv.yaml — 코드 저장용 볼륨 연결

| values.yaml 위치 | 넣을 값 |
|---|---|
| `gitalyVolume.pvName` | 클러스터에서 중복되지 않는 PV 이름 |
| `gitalyVolume.csi.driver` | AWS 일반 EBS: `ebs.csi.aws.com` / NHN NKS: `cinder.csi.openstack.org` |
| `gitalyVolume.csi.volumeHandle` | 미리 생성한 코드 저장용 클라우드 볼륨 ID |
| `gitalyVolume.csi.fsType` | 해당 볼륨의 실제 파일시스템. 예: `ext4` |
| `gitalyVolume.nodeAffinity` | 볼륨을 연결할 수 있는 노드의 실제 영역 라벨·값 |
| `upstream.gitlab.gitaly.persistence.size` | 기존 볼륨 크기에 맞춘 용량. 예: `50Gi` |

기존 볼륨을 가리키는 PV를 생성합니다. PVC는 Gitaly StatefulSet이 생성하고 연결합니다. 클라우드 볼륨 자체를 새로 만드는 파일은 아닙니다.

## validate.yaml — 입력값 검사

주소·볼륨 정보·인증값에 빈 값이나 `CHANGE_ME`가 남으면 설치를 중단합니다. Gitaly 저장소 구성도 검사합니다. 실제 서버 접속·볼륨 마운트·인증서 유효성은 별도 확인해야 합니다.
