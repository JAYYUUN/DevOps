# 검증

- 원본 CICD.zip의 gitlab·jenkins·argocd 파일 39개와 결과 폴더의 파일 내용을 바이트 단위로 비교: 동일.
- integration Helm lint/template, 필수 입력·중복 프로젝트·잘못된 상대 경로 거부 확인.
- 초기 토큰이 Secret에만 들어가고 ConfigMap에는 포함되지 않는지 확인.
- API 모의 검증 5건: 최초 연결, 재실행 시 토큰·예제·최초 빌드 중복 방지, 기존 소스 미변경, 비관리 리소스 덮어쓰기 차단, Jenkinsfile 누락·프로젝트 변경 처리.
- Python CI 예제 테스트 2건 통과.

실제 GitLab·Jenkins·Argo CD 서버에서 새 연동을 실행하지 않았습니다. Jenkins Groovy API의 실제 실행, 프로젝트 토큰 발급 권한, Agent 기동, 실제 CI·Argo 동기화는 현장에서 확인해야 합니다. 원본 설치 모듈의 검증 상태와 새 연동의 검증 범위는 별개입니다.
