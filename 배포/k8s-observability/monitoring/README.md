# Monitoring — 메트릭 모니터링

공식 `prometheus-community/kube-prometheus-stack` **92.11.0**을 사용합니다.

## 구성요소

| 구성요소 | 역할 |
|---|---|
| Prometheus Operator | Prometheus 및 ServiceMonitor 등 관리 |
| Prometheus | 메트릭 수집·저장·PromQL 조회 |
| node-exporter | 노드 CPU·메모리·디스크·네트워크 메트릭 |
| kube-state-metrics | Pod·Deployment·Node 등 Kubernetes 객체 상태 |
| kubelet/cAdvisor | 컨테이너 CPU·메모리 사용량 |
| Alertmanager | Prometheus 알림 처리·전달 |
| Grafana | 메트릭 대시보드 및 Loki 로그 조회 |

## 파일 및 설정

**`values.yaml`**: 공식 차트 기본값을 사용하므로 현재 `{}`입니다. 메트릭 보존 기간, Prometheus PVC, Grafana 설정 등 변경이 필요할 때 이 파일에 추가합니다.

**`loki-datasource.yaml`**: Grafana의 Loki 데이터소스를 자동 등록합니다.

| 항목 | 의미 |
|---|---|
| `name`, `uid`, `type` | 데이터소스 이름·고유 ID·종류 (`loki`) |
| `access: proxy` | Grafana 서버에서 Loki에 접근 |
| `url` | Loki Gateway의 Kubernetes 내부 서비스 주소 |
| `isDefault: false` | 기본 데이터소스를 변경하지 않음 |
| `editable: false` | UI에서 데이터소스 수정 제한 |
| `jsonData.maxLines` | 조회 시 최대 로그 줄 수 |

`observability` 네임스페이스나 Loki 서비스 이름을 바꾸면 `url`도 함께 변경합니다.

## 적용

프로젝트 루트에서 `helmfile sync` 실행. Grafana 접속 방법은 루트 `README.md`를 참고합니다.
