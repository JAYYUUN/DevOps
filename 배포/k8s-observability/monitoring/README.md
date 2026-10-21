# monitoring — 메트릭 및 Grafana

공식 `prometheus-community/kube-prometheus-stack` **92.11.0** 차트를 배포합니다.

| 파일 | 역할 |
|---|---|
| `values.yaml` | Prometheus/Grafana/Alertmanager 차트 기본 설정의 오버라이드 (현재 `{}`) |
| `loki-datasource.yaml` | Grafana에 Loki 데이터소스 자동 등록 |

Grafana 데이터소스 URL은 같은 클러스터 `observability` 네임스페이스의 `loki-gateway` Service를 사용합니다. **네임스페이스나 서비스 이름을 변경했다면 URL도 수정**해야 합니다.

```bash
kubectl get pods -n observability
kubectl get svc monitoring-grafana loki-gateway -n observability
kubectl port-forward -n observability svc/monitoring-grafana 3000:80
```

브라우저에서 `http://127.0.0.1:3000` → Explore → Loki. 자동 데이터소스 등록만으로 Pod 로그가 수집되지는 않습니다. 로그 수집기(Alloy)는 이 저장소 범위 밖입니다.
