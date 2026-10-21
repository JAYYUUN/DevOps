# Kubernetes Observability

Kubernetes **메트릭 모니터링과 로그 조회**를 Helmfile로 구성한 프로젝트입니다. 공식 Helm Chart의 버전을 고정하고, 클라우드별 값만 별도로 입력하도록 구성했습니다.

## 구성

```text
Kubernetes
├─ 메트릭 모니터링: kube-prometheus-stack
│  ├─ Prometheus Operator  : Prometheus 및 모니터링 리소스 관리
│  ├─ Prometheus           : 메트릭 수집·저장·조회
│  ├─ node-exporter        : 노드 CPU·메모리·디스크 등 OS 메트릭
│  ├─ kube-state-metrics   : Pod·Deployment·Node 등 Kubernetes 리소스 상태
│  ├─ kubelet/cAdvisor     : 컨테이너 자원 사용량 메트릭
│  ├─ Alertmanager         : 알림 그룹화·전달
│  └─ Grafana              : 대시보드 및 로그 조회 화면
└─ 로깅: Loki
   ├─ Loki Gateway         : 로그 수신·조회 API 진입점
   ├─ Loki SingleBinary    : 로그 저장·검색 처리
   ├─ S3 Object Storage    : 로그 청크·인덱스 저장
   └─ PVC                  : WAL·캐시 등 로컬 데이터

Grafana ── Prometheus (메트릭 조회)
        └─ Loki       (로그 조회)
```

**적용 구성:** kube-prometheus-stack `92.11.0`, Loki Helm Chart `19.0.2`, Loki 단일 인스턴스 및 S3 저장, Grafana Loki 데이터소스 자동 등록. Prometheus/Grafana 동작과 Loki 로그 전송·조회 및 Grafana Explore 조회까지 완료한 구성입니다.

> **로그 수집기(Fluentd/Fluent Bit/Alloy)는 포함하지 않았습니다.** 현재 Loki는 로그 수신·저장·조회 역할이며, Pod 로그 자동 수집은 별도 구성입니다.

## 파일 안내

| 경로 | 내용 |
|---|---|
| `helmfile.yaml` | 차트·버전·배포 순서 |
| `monitoring/` | Prometheus 스택 및 Grafana 설정 |
| `loki/` | Loki, S3, PVC 설정 |
| `environments/` | 클라우드별 입력값 |
| `scripts/` | 환경값 로딩·상태 조회 |

설정 항목의 의미와 수정 방법은 각 폴더의 `README.md`에 정리했습니다.

## 설치

**준비:** Kubernetes 접근 권한, `kubectl`, `helm`, `helmfile`, `bash`, S3 호환 Object Storage 버킷·인증키, PVC용 StorageClass.

```bash
cd k8s-observability
cp environments/.env.example environments/.env
# environments/.env의 빈 값 입력 (environments/README.md 참고)
source scripts/load-env.sh

kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic loki-s3-credentials -n observability \
  --from-literal=AWS_ACCESS_KEY_ID='ACCESS_KEY' \
  --from-literal=AWS_SECRET_ACCESS_KEY='SECRET_KEY'

helmfile repos
helmfile sync
./scripts/check.sh
```

이미 `loki-s3-credentials` Secret이 있으면 생성 명령은 생략합니다. `.env`와 인증키는 GitHub에 올리지 않습니다.

## Grafana 접속

Bastion에서:

```bash
kubectl port-forward -n observability svc/monitoring-grafana 3000:80
```

Bastion을 경유하는 PC라면 별도 터미널에서 SSH 터널을 엽니다.

```bash
ssh -N -i /path/to/key.pem -p SSH_PORT -L 3000:127.0.0.1:3000 USER@BASTION_IP
```

브라우저 `http://127.0.0.1:3000` → **Explore → Loki**. 관리자 비밀번호 조회:

```bash
kubectl get secret monitoring-grafana -n observability -o jsonpath='{.data.admin-password}' | base64 -d; echo
```
