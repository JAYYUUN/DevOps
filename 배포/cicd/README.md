# CI/CD

GitLab은 코드·배포 정의를 보관하고, Jenkins는 CI를 실행하며, Argo CD는 배포 저장소의 변경을 Kubernetes에 반영합니다.

## 구성

| 경로 | 용도 |
|---|---|
| `gitlab/` | 기존 GitLab 설치 모듈 |
| `jenkins/` | 기존 Jenkins 설치 모듈 |
| `argocd/` | 기존 Argo CD 설치 모듈 |
| `integration/` | 세 도구의 인증정보·Pipeline·배포 저장소·Application을 연결하는 별도 Helm Chart |

세 설치 모듈은 독립적으로 사용합니다. 연동은 세 도구 설치 후 한 번 실행합니다.

## 연동 흐름

1. 소스 저장소의 지정 브랜치에 push합니다.
2. Jenkins가 Git 변경을 감지하고 해당 저장소의 `Jenkinsfile`을 실행합니다.
3. CI 성공 후 Jenkins가 별도 배포 저장소를 갱신합니다.
4. Argo CD가 배포 저장소를 감시하고 대상 네임스페이스에 반영합니다.

기본 연결은 Jenkins SCM 폴링(약 2분 간격)과 Argo CD의 Git 감시를 사용합니다. 즉시 실행용 Webhook은 등록하지 않습니다. 기존 플러그인·Chart를 변경하지 않고 연결하기 위한 방식입니다.

예제는 테스트가 성공한 소스 commit SHA를 배포 저장소의 ConfigMap에 기록합니다. 컨테이너 이미지 빌드·Registry push는 포함하지 않습니다. 실제 서비스는 소스 저장소의 Jenkinsfile에서 빌드·테스트·이미지 push·배포 정의 변경 단계로 바꿉니다.

## 준비

- 각 폴더의 README대로 GitLab·Jenkins·Argo CD를 먼저 설치합니다. 이름·네임스페이스 기본값은 각각 `gitlab`, `jenkins`, `argocd`입니다.
- GitLab에서 `api` 범위의 초기 연결용 Access Token을 하나 발급합니다. 두 프로젝트의 Maintainer 이상 권한이 필요합니다. 프로젝트 자동 생성 시 대상 GitLab namespace에도 생성 권한이 있어야 합니다.
- 기본 Jenkins 관리자 Secret을 변경했다면 `integration/values.yaml`의 Secret 이름·키를 맞춥니다.
- 빌드 Agent를 실행할 클러스터 자원과 이미지 다운로드 통신이 필요합니다. 기본 Controller에서는 CI를 실행하지 않습니다.

이 초기 GitLab 토큰은 API에 처음 접근하기 위한 인증값입니다. 이후 Jenkins 소스 읽기·배포 저장소 쓰기·Argo CD 배포 저장소 읽기 토큰은 연동 Job이 프로젝트별로 발급·등록합니다.

## 입력 — integration/values.yaml

| 항목 | 넣을 값 |
|---|---|
| `gitlab.bootstrapToken` | 위에서 발급한 `api` 범위 토큰. root 비밀번호가 아님 |
| `source.project` | 소스 GitLab 프로젝트 전체 경로. 예: `root/cicd-app` |
| `deployment.project` | 배포 전용 프로젝트 전체 경로. 예: `root/cicd-gitops` |
| `source.branch`, `source.pipelineFile` | CI 대상 브랜치·Pipeline 파일. 기본 `main`, `Jenkinsfile` |
| `deployment.branch`, `deployment.path` | 배포 저장소의 브랜치·YAML 디렉터리. 기본 `main`, `apps/demo` |
| `deployment.namespace` | Kubernetes 배포 대상. 기본 `cicd-demo` |

`root`는 예시이며 실제 GitLab 사용자/그룹 경로를 입력합니다. 사용자·그룹 namespace는 미리 존재해야 합니다. 기본값은 없는 프로젝트를 private으로 생성하고 **빈 저장소에만** 예제를 넣습니다. 기존 프로젝트는 그대로 사용하며, 소스 저장소에는 지정된 Jenkinsfile이 있어야 합니다.

직접 만든 프로젝트·Pipeline만 사용하려면 다음 두 값을 끕니다.

```yaml
gitlab:
  createProjectsIfMissing: false
demo:
  seedEmptyRepositories: false
```

초기 토큰을 별도 Secret으로 관리하려면 같은 `cicd-system` namespace에 키 `api-token`을 가진 Secret을 준비하고 `gitlab.existingSecret`에 이름을 지정합니다. 실제 토큰이 들어간 values는 Git에 올리지 않습니다. Helm release에도 저장됩니다.

기본 연동 URL은 Kubernetes 내부 Service 주소입니다. 설치 이름·네임스페이스가 다르면 `gitlab.url`, `jenkins.url`, `jenkins.namespace`, `argocd.namespace`를 수정합니다. Git 저장소 연결도 GitLab 내부 HTTP Service를 사용하므로 동적 LB IP·PC hosts·자체 서명 CA를 연동용으로 입력하지 않습니다. **연동 트래픽은 클러스터 내부 HTTP이며 웹 HTTPS 설정은 각 모듈 그대로 사용합니다.**

## 실행

`cicd` 폴더에서 실행합니다.

```bash
helm lint ./integration -f ./integration/values.yaml
helm upgrade --install cicd-integration ./integration \
  --namespace cicd-system --create-namespace \
  -f ./integration/values.yaml \
  --wait --wait-for-jobs --timeout 20m
```

설치·업그레이드 후 Helm hook Job이 API로 다음을 구성하고 종료합니다.

- 선택한 소스·배포 프로젝트 확인 또는 생성, 빈 저장소 예제 초기화
- 프로젝트별 읽기·쓰기 토큰 발급 및 Kubernetes Secret에 재사용 상태 보관
- Jenkins 인증정보·Pipeline 작업·Git 변경 감지 등록, 기본값에서는 최초 빌드 요청
- Argo CD 읽기 전용 저장소 Secret·전용 AppProject·Application 등록

추가 플러그인은 설치하지 않습니다. 기본 Jenkins Chart에 포함된 Git·Pipeline·Kubernetes·Credentials 관련 플러그인과 관리자 Script Console API를 사용합니다. 관리자가 해당 플러그인이나 Script Console을 제한했다면 먼저 구성을 확인합니다.

## 확인

```bash
kubectl get applications,appprojects -n argocd
kubectl get configmap cicd-demo -n cicd-demo -o jsonpath='{.data.revision}'; echo
```

Jenkins의 `cicd-pipeline` 빌드가 성공하고, Argo CD의 `cicd-demo`가 Synced이면 예제 연결이 완료된 것입니다. ConfigMap의 `revision`이 소스 commit SHA로 바뀝니다. Job 성공은 설정·빌드 요청 성공이며 CI·Argo 동기화 완료까지 기다리는 것은 아닙니다.

기본 Argo 설정은 자동 동기화·self-heal을 켜고 자동 삭제(prune)는 끕니다. 기존 배포 저장소를 지정하면 해당 경로의 리소스가 즉시 반영될 수 있으므로 `argocd.automated: false`로 시작할 수 있습니다. AppProject는 지정 배포 저장소·대상 namespace로 제한합니다.

실패한 초기화 Job은 남습니다.

```bash
kubectl get jobs -n cicd-system
kubectl logs -n cicd-system job/cicd-integration-link-bootstrap
```

설정을 수정한 뒤 같은 Helm upgrade 명령으로 재실행합니다. 기존에 이 연동이 만든 토큰·Jenkins 작업·Argo 리소스는 갱신하고, 다른 소유자의 같은 이름 리소스는 덮어쓰지 않습니다. 생성된 토큰을 수동 폐기한 경우 상태 Secret 처리 또는 새 연동 릴리스가 필요합니다.

## 관리

- 프로젝트별 토큰 기본 유효기간은 30일입니다. 자동 갱신 CronJob은 없으므로 만료 전 재실행이 필요합니다. 재실행은 만료 하루 이내의 토큰을 교체합니다. `gitlab.tokenLifetimeDays`로 기간을 지정합니다.
- 연동 Job은 Jenkins 관리자 Secret을 읽고 관리자 API로 설정합니다. Argo namespace에는 이 연동의 저장소·Project·Application을 만듭니다. 권한은 `integration/templates/rbac.yaml`에 명시되어 있습니다.
- 연동 상태 Secret에는 프로젝트 토큰이 있으므로 보호합니다. Job 로그는 인증정보를 출력하지 않도록 작성했습니다.
- Helm uninstall은 이 Chart의 Job·RBAC·설정만 제거합니다. API로 만든 프로젝트·토큰·Jenkins 작업·Argo 리소스·상태 Secret은 자동 삭제하지 않습니다. 해제할 때 해당 항목을 명시적으로 정리합니다.
- 기존 서비스의 Helm upgrade는 JCasC 설정을 재적용할 수 있습니다. 연동 작업을 삭제하거나 덮어쓴 경우 이 integration 릴리스를 다시 실행합니다.

[GitLab 프로젝트 토큰 API](https://docs.gitlab.com/api/project_access_tokens/) · [Jenkins Script Console](https://www.jenkins.io/doc/book/managing/script-console/) · [Argo CD 선언적 설정](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
