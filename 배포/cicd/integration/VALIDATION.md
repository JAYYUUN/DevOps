# 검증 범위

- integration Helm lint/template 및 렌더링된 YAML 파싱 통과.
- Jenkins 원본 Chart와 별도 플러그인 override를 함께 렌더링하여 GitLab 플러그인 포함 확인.
- 초기 GitLab 토큰·Registry 비밀값이 ConfigMap에 포함되지 않고 Secret으로 분리되는지 확인.
- API 모의 검증 7건: 초기 연결·재실행, Webhook 중복 방지·Secret 재사용, 기존 허용 목록 보존, push/pull 인증 분리, 기존 소스 보존, 비관리 리소스 보호, Jenkinsfile 누락·프로젝트 변경 처리.
- 이미지 갱신 검증: Kustomize 이미지 주소·태그 변경, 나머지 설정 보존, 같은 태그 재실행, 잘못된 revision·누락 이미지 거부.
- 필수값·Registry 주소 형식·잘못된 상대 경로·동일 프로젝트 거부, 기존 초기 Secret 사용 렌더링 확인.
- 예제 Python 테스트 통과.
- gitlab·jenkins·argocd의 원본 39개 파일은 바이트 단위로 동일함을 확인.

실제 클러스터에서 새 연동을 실행하지 않았습니다. Jenkins Groovy·플러그인 실제 구동, BuildKit 노드 지원, Registry 인증·이미지 업로드, GitLab Webhook 전송, Argo CD 실제 동기화는 현장 검증이 필요합니다. 원본 설치 모듈의 검증 상태와 새 연동의 검증 범위는 별개입니다.
