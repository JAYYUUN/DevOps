# Kubernetes Observability — Helmfile

공식 Helm Chart를 **Helmfile로 묶어 재현 가능하게 배포**하는 프로젝트입니다. 커스텀 Helm Chart가 아닙니다.

## 구성과 역할

```text
Kubernetes cluster
├─ monitoring (kube-prometheus-stack 92.11.0)
│  ├─ Prometheus: 메트릭 수집/조회
│  ├─ Alertmanager: 알림 처리
│  └─ Grafana: 메트릭 대시보드 + Loki 로그 조회
└─ loki (grafana-community/loki 19.0.2)
   ├─ Loki Gateway: Grafana 조회 및 로그 수신 진입점
   └─ Loki SingleBinary: 로그 인덱싱/조회
      ├─ S3 호환 Object Storage: 청크/인덱스 영구 저장
      └─ PVC 10Gi: WAL/캐시 등 로컬 작업 데이터
```

**확인된 범위:** Prometheus/Grafana 동작, Loki API 수집·조회, Grafana Explore에서 테스트 로그 조회. **아직 확인하지 않은 범위:** S3에 실제 객체가 기록되었는지, 새 클러스터에 이 템플릿을 처음부터 재배포했을 때의 성공 여부. **미포함:** Alloy 및 Kubernetes Pod 로그 자동 수집.

## 폴더

| 경로 | 설명 |
|---|---|
| `helmfile.yaml` | 차트 저장소, 버전, 배포 순서 |
| `environments/` | 환경별 S3 엔드포인트·버킷·StorageClass 입력값 |
| `loki/` | Loki 단일 바이너리, S3, PVC, 권한 초기화 설정 |
| `monitoring/` | Prometheus/Grafana 및 Loki 데이터소스 자동 등록 |
| `scripts/` | 환경변수 로딩, 배포 상태 확인, 기존 설치값 백업 |

각 폴더의 `README.md`에 해당 파일의 설정법과 검증 방법이 있습니다.

## 설치 전 준비

- Kubernetes 접근 가능한 PC/Bastion, `kubectl`, `helm`, `helmfile`, `bash`
- S3 호환 Object Storage의 **생성된 버킷**, 접근 키, 비밀 키, S3 엔드포인트 및 리전
- 동적 PVC 프로비저닝이 가능한 **StorageClass**와 적절한 노드 자원
- S3로 나가는 네트워크 및 권한 (`ListBucket`, `GetObject`, `PutObject`, `DeleteObject` 등 필요한 작업)

## 실행 (Linux/Bastion)

```bash
cd k8s-observability
cp environments/.env.example environments/.env
# environments/.env 파일에 4개 값을 채운다 (environments/README.md 참고)
source scripts/load-env.sh
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic loki-s3-credentials -n observability \
  --from-literal=AWS_ACCESS_KEY_ID='YOUR_ACCESS_KEY' \
  --from-literal=AWS_SECRET_ACCESS_KEY='YOUR_SECRET_KEY'
helmfile repos
helmfile template > /tmp/observability-rendered.yaml
helmfile sync
./scripts/check.sh
```

기존 Secret이 있으면 `kubectl create secret`을 다시 실행하지 않습니다. 키는 명령 기록에 남을 수 있으므로 실제 운영 시에는 파일/외부 Secret 관리 솔루션 등 안전한 주입 방식을 사용하세요. `helmfile template`에는 Secret 값이 들어가지 않지만 출력물에 환경 설정값은 포함됩니다.

## Grafana 접속 및 검증

Bastion 터미널에서:

```bash
kubectl port-forward -n observability svc/monitoring-grafana 3000:80
```

원격 Windows PC에서는 별도 PowerShell에서 SSH 터널 연결:

```powershell
ssh -N -i "C:\path\to\bastion.pem" -p YOUR_SSH_PORT -L 3000:127.0.0.1:3000 ubuntu@BASTION_IP
```

`http://127.0.0.1:3000` 접속 → **Explore → Loki**. Grafana 비밀번호:

```bash
kubectl get secret monitoring-grafana -n observability -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

이전 테스트 로그가 존재하면 `{job="loki-test"}`로 조회합니다. 새 클러스터에는 이 테스트 로그가 자동 생성되지 않습니다.

## 운영 시 유의사항

- **PVC는 제거하지 않았습니다.** S3는 장기 저장소, PVC는 WAL/캐시용입니다.
- Loki는 `replicas: 1`, `replication_factor: 1`이므로 **고가용성 구성은 아닙니다.**
- `auth_enabled: false`는 내부 클러스터 단일 테넌트 기준입니다. 외부 공개 시 인증/네트워크 제어를 설계하세요.
- `initContainer`가 root로 볼륨 권한을 수정합니다. Restricted Pod Security 정책 클러스터에서는 수정이 필요합니다.
- StorageClass, S3 주소, 버킷, 리전, 인증키는 환경마다 다릅니다.
- **차트 버전은 이전 성공 환경 기준으로 고정**했으나, 현재 실제 릴리스 values와 이 템플릿의 완전한 동일성은 확인되지 않았습니다. 배포 전 `helm get values`와 비교하세요.
