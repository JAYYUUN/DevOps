# 검증 결과

- 공식 Chart를 내려받고 Chart.lock 생성. Argo CD 10.11.1 / Envoy Gateway 1.9.2 고정.
- Helm 3.19.0 lint 및 실제 값을 입력한 values 파일로 template 통과.
- PV·PVC·Ingress 없음. 전용 내부 Redis 1개, API Server·Repo Server·Application Controller·전용 Envoy Controller 확인.
- Dex·Notifications Pod 없음. ApplicationSet replicas 0 확인.
- Argo CD CRD 3개만 생성·keep 확인. 공통 Gateway·Envoy CRD 중복 생성 없음.
- GatewayClass·Controller 식별자 일치, HTTPRoute의 전용 Gateway 및 argocd-server:80 연결 확인.
- Gateway TLS 종료와 내부 HTTP 설정 일치 확인.
- OpenSSL 인증서 체인·argocd.internal 도메인 검증 통과.
- 저장소 연결 비활성 시 Secret 없음, 활성 시 공식 repository 라벨·인증값 반영 확인.
- LB 설정 누락·저장소 인증 누락·도메인 불일치·공통 CRD 중복 설치·내부 Redis 비활성 입력 거부 확인.
- 공식 CRD 스키마로 EnvoyProxy·GatewayClass·Gateway·HTTPRoute 및 예제 Application 검사.

실제 클러스터 배포, 기존 인증서 lookup 재사용 실행, 내부 LB 생성, DNS, GitLab 인증·CA 신뢰, Application 동기화, 백업·복구는 미검증입니다. 기본값의 CHANGE_ME를 실제 CSP 값으로 바꾼 후 설치합니다.
