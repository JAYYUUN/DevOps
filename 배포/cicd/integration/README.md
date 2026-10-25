# CI/CD 연동 모듈

GitLab Push Webhook → Jenkins 테스트·BuildKit 이미지 빌드·Registry 업로드 → GitLab Kustomize 이미지 태그 변경 → Argo CD 배포를 연결합니다.

입력값·Registry 준비·적용 순서·확인은 [상위 README](../README.md)를 참고합니다. 기존 세 설치 모듈을 먼저 배포하고 `overrides/jenkins.yaml`을 기존 Jenkins values와 함께 적용한 뒤 이 Chart를 설치합니다.

`files/`는 API 초기 설정 코드, `examples/`는 새 빈 저장소용 예제, `templates/`는 초기화 Job·Secret·RBAC입니다. 기존 저장소의 코드는 자동 교체하지 않습니다.
