# 검증 기록

2026-10-24, Helm v3.19.0 / 공식 GitLab Chart 10.5.1 / GitLab 19.5.1.

## 완료

- helm dependency update로 Chart.lock 생성, 고정 버전 공식 Chart 아카이브 포함.
- 실제 비밀값 없이 테스트용 외부 서비스 주소·볼륨 ID를 넣어 helm lint 통과.
- AWS 일반 EBS CSI 및 NHN Cinder CSI 값을 같은 values 구조에 넣어 각각 helm template 통과.
- 각 렌더링 47개 객체의 YAML 파싱 확인.
- PostgreSQL·Redis·MinIO 워크로드를 설치하지 않고 Gitaly StatefulSet만 존재함 확인.
- 외부 PostgreSQL과 캐시/영속 Redis 주소가 앱 설정에 반영됨 확인.
- 외부 DB·Redis·Rails Object Storage·Registry·백업·TLS Secret 참조 확인.
- PGSSLMODE=verify-full과 PGSSLROOTCERT 환경변수 및 사용자 CA Secret 참조 렌더링 확인.
- Gitaly PV와 StatefulSet PVC의 class·용량·selector·claimRef 일치 확인.
- release·namespace 변경 및 storageClass '-' 설정 때 연결 일치 확인.
- PV Retain/keep 설정, Gitaly 전용 노드 selector와 cgroup init container 확인.
- GitLab·Registry Ingress 2개, Toolbox 백업 CronJob 생성 확인.
- 필수 입력 미설정, topology 자리표시자, 지원하지 않는 다중 Gitaly 저장소 입력 차단 확인.

## 실제 환경에서 남은 검증

Kubernetes에 설치하거나 외부 서비스·실제 디스크에 접속하지 않았습니다. 외부 DB 버전·확장·권한·TLS와 Redis 인증·TLS, S3 호환성과 버킷 권한, Ingress Controller 및 DNS·인증서, Gitaly 노드 런타임·cgroup·CSI 연결·파일시스템 권한, 마이그레이션·로그인·HTTPS push/clone·Pod 재생성 후 코드 유지, 백업·별도 환경 복구가 필요합니다.

부하·HA·RPO/RTO는 검증하지 않았습니다. 공식 참조 아키텍처의 배치 방향에 맞춘 시작용 구성으로, 공식 S/M/L/XL 사이징을 그대로 적용한 배포가 아닙니다. 단일 Gitaly는 자동 장애 전환 구성이 아닙니다.

## Secret 생성 검증

테스트 값으로 7개 Secret 생성·DB 비밀번호·Object Storage 세 연결 형식 일치 확인. create=false 생성 생략, 미입력 인증값 차단 확인. 실제 접속은 미검증. 체크섬 파일은 Chart 루트로 이동.

## 자체 서명 TLS 자동 구성

수동 TLS 입력·Secret 생성 제거. 공식 selfsign hook Job 생성과 CA·wildcard·chain Secret 생성 명령 확인. GitLab·Registry Ingress가 같은 release-wildcard-tls를 참조하는지 확인. 외부 Ingress 사용을 위해 상위 Chart의 TLS helper에서 해당 Secret을 명시적으로 지정. Helm lint 통과. 실제 Job 실행·CA 신뢰 등록·HTTPS 접속과 인증서 수명주기는 실환경 미검증.
