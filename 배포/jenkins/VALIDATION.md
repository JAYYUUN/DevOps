# 검증 결과

- Helm 3.19.0 lint 및 의존성을 포함한 template 통과.
- 공식 의존성 다운로드 후 Chart.lock 생성. 설치 시 사용할 Chart 원본을 charts/에 포함.
- Envoy Chart에 포함된 CRD 스키마로 EnvoyProxy·GatewayClass·Gateway·HTTPRoute 유효성 검사 통과.
- CRD·Ingress 중복 생성 없음. Jenkins 전용 Controller 식별자와 GatewayClass 일치 확인.
- 공식 Jenkins HTTPRoute가 전용 Gateway의 https 리스너와 Jenkins Service 8080으로 연결됨을 확인.
- NHN 내부 LB annotation과 PV Retain·PVC keep·20Gi 기존 볼륨 마운트 참조 확인.
- OpenSSL로 생성 인증서 체인과 jenkins.internal 호스트명 검증 통과.
- 필수 값 누락·CHANGE_ME 파일시스템·CRD 중복 설치·도메인 불일치 거부 확인.
- XFS·30Gi·다른 도메인 설정 렌더링 확인.

실제 클러스터 배포, 기존 Secret lookup 재사용 실행, CSI 마운트·권한, LB 생성·DNS·Webhook·CI 실행·백업 복구는 미검증입니다. 인증서 재사용 로직은 코드에 포함되어 있으며 live cluster 확인이 필요합니다.
