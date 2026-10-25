# 연동 Chart

GitLab·Jenkins·Argo CD 설치 후 API로 인증정보·Pipeline·Application을 연결하는 일회성 Helm hook Job입니다. 세 도구의 설치 파일과 플러그인 설정은 수정하지 않습니다.

입력값·실행·확인 방법은 상위 [README](../README.md)를 참고합니다. `files/bootstrap.py`는 GitLab/Jenkins/Kubernetes API 초기 설정, `files/configure.groovy`는 Jenkins 인증정보·작업 등록을 담당합니다. `examples/source/Jenkinsfile`은 GitLab 소스 저장소에서 실행할 CI 예제입니다.

기본값은 Git 폴링을 사용하며 Webhook은 등록하지 않습니다. 예제는 Python 테스트 후 ConfigMap revision을 배포합니다. 이미지 빌드·Registry push는 실제 프로젝트의 Jenkinsfile에 추가합니다.
