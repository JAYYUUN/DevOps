# CI/CD

GitLab에 코드를 push하면 Jenkins가 테스트·컨테이너 이미지 빌드를 실행하고, Argo CD가 Kubernetes에 배포하도록 연결합니다. 이미지는 별도로 준비한 클라우드 Container Registry에 보관합니다.

## 구성

| 폴더 | 역할 |
|---|---|
| `gitlab/` | GitLab 설치. 소스코드와 배포 설정 보관 |
| `jenkins/` | Jenkins 설치. 테스트·이미지 빌드 실행 |
| `argocd/` | Argo CD 설치. Git의 배포 설정을 Kubernetes에 적용 |
| `integration/` | Webhook·인증정보·Jenkins 작업·Argo CD 배포 연결 |

세 도구는 각 README대로 먼저 설치합니다. 연동 설정은 그다음 진행합니다. 기존 세 모듈의 파일은 수정하지 않았습니다.

## 전체 동작

1. 개발자가 GitLab **소스 저장소**에 코드를 push합니다.
2. GitLab이 **Webhook**으로 Jenkins에 변경을 알립니다.
3. Jenkins가 소스코드와 **Jenkinsfile**을 가져옵니다. Jenkinsfile은 테스트·빌드 순서를 적은 파일이며 소스 저장소에 보관합니다.
4. 테스트가 성공하면 Jenkins Agent Pod의 **BuildKit**이 Dockerfile로 이미지를 빌드합니다.
5. Jenkins가 이미지를 **클라우드 Registry에 업로드**합니다. 이미지 태그는 소스 커밋번호입니다.
6. 업로드가 성공하면 GitLab **배포 저장소**의 이미지 주소·태그를 수정하여 push합니다.
7. Argo CD가 배포 저장소 변경을 감지하고 Kubernetes API에 배포 설정을 적용합니다.
8. Kubernetes 워커 노드가 Registry에서 이미지를 다운로드하여 컨테이너를 실행합니다.

Jenkins는 소스 저장소의 Push Webhook으로 실행됩니다. 배포 저장소에는 Jenkins 실행용 Webhook을 등록하지 않습니다. Argo CD는 Git 변경을 주기적으로 확인하므로 CI 완료 후 배포까지 잠시 걸릴 수 있습니다.

## 먼저 준비할 것

- GitLab·Jenkins·Argo CD를 설치합니다. 기본 설치 이름과 네임스페이스는 각각 `gitlab`, `jenkins`, `argocd`입니다.
- 클라우드 Registry와 이미지 저장소를 준비합니다. 아래 Registry 준비 절차를 참고합니다.
- GitLab에서 초기 설정용 Access Token을 발급합니다. `api` 범위가 필요합니다. 기본값에서는 내부 Jenkins 주소를 Webhook 허용 목록에 등록하므로 **관리자 토큰**을 사용합니다. 관리자 모드를 적용한 환경은 해당 API 접근 권한도 확인합니다.
- Jenkins Agent가 실행될 CPU·메모리와 네트워크를 준비합니다. 기본 예제는 Agent에서 Git·Python·BuildKit 컨테이너를 실행합니다. Docker Hub 이미지와 PyPI 패키지 다운로드, 클라우드 Registry 접속이 필요합니다.

### 클라우드 Registry 연결 준비

1. 사용할 클라우드의 Container Registry(NCR 등)를 생성하거나 기존 Registry를 선택합니다.
2. 사용할 이미지 저장소를 준비합니다. 콘솔에서 안내하는 **Registry 접속 주소**와 **프로젝트·이미지 경로**를 확인합니다.
3. 해당 서비스의 Docker 로그인 안내에 따라 **계정·인증 키 또는 토큰**을 발급합니다.
4. Jenkins가 사용할 인증정보에 **이미지 업로드 권한**, Kubernetes가 사용할 인증정보에 **이미지 다운로드 권한**을 부여합니다. 하나의 인증정보에 두 권한이 있으면 공통 값으로 한 번 입력할 수 있습니다.
5. Jenkins Agent와 Kubernetes 워커 노드에서 Registry 주소를 조회하고 HTTPS로 접근할 수 있도록 DNS·방화벽·클라우드 접근 제한을 확인합니다.

이 인증정보는 GitLab·Jenkins 로그인 계정과 별개입니다. 서비스에 따라 Access Key가 사용자 이름이고 Secret Key가 비밀번호일 수 있으므로, **해당 Registry의 Docker 로그인 안내에서 username/password에 해당하는 값**을 확인합니다.

현재 연동은 계정·비밀번호 또는 토큰으로 Registry에 로그인하는 방식입니다. 클라우드 리소스 생성·IAM 역할 연동·임시 토큰 자동 발급과 갱신은 포함하지 않습니다. 토큰이 만료되면 새 값을 입력해 다시 적용해야 합니다. 공인 HTTPS 인증서를 사용하는 Registry를 기준으로 합니다.

NCR의 NHN Cloud·NAVER Cloud 서비스가 아직 확정되지 않았으므로 콘솔 메뉴·키 명칭은 공통 안내로 작성했습니다.

## 직접 입력할 값

`integration/values.yaml`의 다음 값을 변경합니다. 나머지 설정은 기본 예제를 실행할 때 그대로 사용할 수 있습니다.

```yaml
gitlab:
  bootstrapToken: CHANGE_ME
source:
  project: CHANGE_ME
deployment:
  project: CHANGE_ME
registry:
  address: CHANGE_ME
  repository: CHANGE_ME
  username: CHANGE_ME
  password: CHANGE_ME
```

| 항목 | 무엇을 넣는가 |
|---|---|
| `gitlab.bootstrapToken` | GitLab 초기 연결용 `api` 토큰. 기본 자동 설정에는 관리자 권한 필요. 로그인 비밀번호가 아님 |
| `source.project` | 소스 프로젝트 전체 경로. 예: `yhjung/myapp` |
| `deployment.project` | 배포 설정 프로젝트 전체 경로. 예: `yhjung/myapp-deploy` |
| `registry.address` | Registry 접속 주소. `https://`와 이미지 경로 제외. 예: `registry.example.com` |
| `registry.repository` | 이미지 경로. 예: `team/myapp`. 주소와 태그는 제외 |
| `registry.username` | Registry에서 발급한 업로드·다운로드 권한이 있는 계정 또는 인증 키 |
| `registry.password` | 위 계정과 짝인 Registry 비밀번호·Secret Key 또는 토큰 |

예를 들어 주소가 `registry.example.com`, 이미지 경로가 `team/myapp`이면 최종 이미지는 `registry.example.com/team/myapp:커밋번호`가 됩니다.

`yhjung` 같은 GitLab 사용자·그룹 경로는 미리 존재해야 합니다. 그 아래 프로젝트가 없으면 기본 설정에서 private 프로젝트를 생성하고, **빈 저장소에만** 예제를 넣습니다. 소스와 배포 프로젝트는 서로 다르게 지정합니다.

실제 인증정보를 입력한 values는 Git에 올리지 않습니다. 입력값은 Helm release 정보에도 저장됩니다.

### 업로드·다운로드 계정을 따로 쓰는 경우

공통 `registry.username/password` 대신 다음 항목을 채웁니다. 두 계정이 같으면 추가할 필요가 없습니다.

```yaml
registry:
  push:
    username: CHANGE_ME
    password: CHANGE_ME
  pull:
    username: CHANGE_ME
    password: CHANGE_ME
```

| 항목 | 넣을 값 |
|---|---|
| `registry.push.username/password` | 이미지 **업로드 권한**이 있는 Registry 계정·인증 키 또는 토큰 |
| `registry.pull.username/password` | 이미지 **다운로드 권한**이 있는 Registry 계정·인증 키 또는 토큰 |

## 자동으로 연결하는 부분

| 대상 | 자동 설정 |
|---|---|
| GitLab | 소스·배포 프로젝트 확인/생성, 저장소별 접근 토큰 발급, 소스 Push Webhook 등록 |
| Webhook | Jenkins 내부 주소로 수신 URL 조합, Secret 생성·보관·재사용 |
| GitLab 내부망 정책 | 기존 허용 목록을 유지하며 Jenkins 호스트 추가 |
| Jenkins | 소스 읽기·배포 쓰기·Registry 업로드 인증정보와 `cicd-pipeline` 작업 등록 |
| Kubernetes | 배포 네임스페이스와 Registry 다운로드 Secret 생성 |
| Argo CD | 배포 저장소 읽기 인증정보, AppProject·Application·자동 동기화 등록 |

도구 사이에는 Kubernetes 내부 Service 주소를 사용합니다. LB IP·PC hosts·웹 인증서는 연동값으로 입력하지 않습니다. 내부 연동은 HTTP이며 기존 웹 HTTPS 설정은 유지합니다.

GitLab 내부망 허용 목록을 관리자가 미리 설정했다면 `gitlab.configureWebhookAllowlist: false`로 바꿀 수 있습니다. 이 경우 초기 토큰은 두 프로젝트에 Maintainer 이상의 권한이 있어야 하며, 프로젝트를 생성한다면 해당 사용자·그룹 아래 생성 권한도 있어야 합니다.

## 기본 예제와 실제 프로젝트

새 빈 소스 저장소에는 다음 파일이 들어갑니다.

| 파일 | 역할 |
|---|---|
| `Jenkinsfile` | 테스트 → 이미지 빌드·업로드 → 배포 설정 갱신 |
| `Dockerfile` | 예제 Python 웹 서버를 컨테이너 이미지로 만드는 방법 |
| `app.py`, `test_app.py` | 예제 프로그램과 테스트 |
| `publish.py` | 배포 저장소의 Kustomize 이미지 주소·태그 변경 |

배포 저장소에는 `apps/myapp/deployment.yaml`과 `kustomization.yaml`을 넣습니다. Kustomize는 Deployment 원본에 이미지 주소·태그를 적용하는 Kubernetes 설정 방식입니다. Argo CD가 이를 처리합니다.

`deployment.yaml`은 `image: cicd-app:pending`을 사용하며, `kustomization.yaml`의 `images`에서 `name: cicd-app` 항목을 Jenkins가 변경합니다. 다운로드용 Secret 참조는 예제 생성 시 자동 입력합니다. 최초 이미지 업로드 전에는 임시 `pending` 이미지로 인해 배포가 준비되지 않을 수 있습니다.

**기존 저장소의 파일은 자동으로 덮어쓰지 않습니다.** 이전 ConfigMap 연동 예제를 이미 GitLab에 생성했다면 새 예제 파일을 직접 반영해야 이미지 빌드 흐름으로 바뀝니다. 기존 프로젝트를 쓰려면 `integration/examples/source/`의 Jenkinsfile·publish.py를 참고해 적용하고, 프로젝트에 맞는 Dockerfile·테스트 명령을 준비합니다. 배포 저장소는 위 Kustomize 구조와 Secret 참조를 준비해야 합니다. 임의의 Helm values나 모든 YAML 구조를 자동 수정하는 구성은 아닙니다.

| 필요할 때만 변경 | 기본값과 의미 |
|---|---|
| `source.branch` | `main`. CI를 실행할 브랜치 |
| `build.testCommand` | `python -m unittest discover -v`. 프로젝트 테스트 명령. 기본 Python 컨테이너에서 실행 |
| `build.context` | `.`. 이미지 빌드에 전달할 소스 폴더 |
| `build.dockerfile` | `Dockerfile`. 소스 저장소 루트 기준 파일 경로 |
| `deployment.branch` | `main`. 배포 설정 브랜치 |
| `deployment.path` | `apps/myapp`. Kustomize 파일이 있는 폴더 |
| `deployment.namespace` | `cicd-demo`. 컨테이너를 실행할 Kubernetes 네임스페이스 |

Java·Node.js 등의 프로젝트는 Jenkinsfile의 테스트 컨테이너·명령도 해당 언어에 맞춰 변경합니다. Jenkinsfile은 소스 저장소에서 관리하므로 이후 CI 절차 변경은 그 저장소에 push합니다.

## 적용

`cicd` 폴더에서 실행합니다.

### 1. Jenkins에 Webhook 플러그인 추가

기존 Jenkins 설정을 그대로 입력 파일로 사용하고, 플러그인 추가 설정을 함께 적용합니다.

```bash
helm upgrade --install jenkins ./jenkins \
  --namespace jenkins --create-namespace \
  -f ./jenkins/values.yaml \
  -f ./integration/overrides/jenkins.yaml \
  --wait --timeout 20m
```

`jenkins/values.yaml`은 기존 배포 때 사용한 실제 볼륨·Gateway 설정이 들어 있는 파일이어야 합니다. 별도 운영 values 파일을 썼다면 그 파일을 사용합니다. 플러그인 적용 중 Jenkins가 재시작될 수 있습니다. 추가로 설치한 플러그인이 있다면 `integration/overrides/jenkins.yaml` 목록에도 포함합니다. 이후 Jenkins 업그레이드에도 같은 추가 설정 파일을 함께 사용합니다.

### 2. 연동 설정 실행

```bash
helm lint ./integration -f ./integration/values.yaml

helm upgrade --install cicd-integration ./integration \
  --namespace cicd-system --create-namespace \
  -f ./integration/values.yaml \
  --wait --wait-for-jobs --timeout 20m
```

임시 초기화 Job이 API로 설정하고 종료됩니다. 기본값에서는 최초 Jenkins 빌드도 요청합니다. **Job 성공은 설정·빌드 요청 완료를 뜻하며, 이미지 빌드·배포 완료까지 기다렸다는 뜻은 아닙니다.**

## 동작 확인

1. Jenkins에서 `cicd-pipeline`의 Console Output을 엽니다. 테스트·이미지 빌드·업로드·배포 저장소 수정 단계가 성공했는지 확인합니다.
2. 클라우드 Registry에서 소스 커밋번호를 태그로 가진 이미지가 생겼는지 확인합니다.
3. GitLab 배포 저장소에서 `kustomization.yaml`의 `newName`·`newTag`가 바뀌었는지 확인합니다.
4. Argo CD에서 `cicd-demo`가 **Synced·Healthy**인지 확인합니다.
5. Kubernetes에서 새 이미지와 Pod 실행 상태를 확인합니다.

```bash
kubectl get applications -n argocd
kubectl get pods -n cicd-demo
kubectl get deployment cicd-demo -n cicd-demo \
  -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
```

소스 코드를 수정해 push한 뒤 Jenkins가 Webhook으로 실행되고 위 이미지 태그가 새 커밋번호로 바뀌면 전체 흐름이 연결된 것입니다. 예제 웹 서비스는 내부 ClusterIP이며 외부 공개용 Gateway는 추가하지 않습니다.

## 실패했을 때

초기 설정이 실패하면 다음 로그를 확인합니다.

```bash
kubectl get jobs -n cicd-system
kubectl logs -n cicd-system job/cicd-integration-link-bootstrap
```

| 증상 | 확인할 부분 |
|---|---|
| Push해도 Jenkins가 실행되지 않음 | GitLab 프로젝트 Webhook의 최근 전송 결과, Jenkins 플러그인, 내부 주소 허용·통신 |
| Registry 업로드 실패 | 주소·업로드 인증정보·권한·네트워크 |
| Pod가 `ImagePullBackOff` | 다운로드 인증정보·권한, 이미지 존재 여부, 워커 노드 통신 |
| 배포 설정 갱신 실패 | 배포 토큰, 브랜치 권한, Kustomize 파일과 `name: cicd-app` 항목 |
| BuildKit 시작 실패 | 노드의 사용자 네임스페이스·보안 정책 지원 |

이미지 빌드는 rootless BuildKit을 사용하며 Docker 소켓·privileged 컨테이너는 연결하지 않습니다. 공식 Kubernetes 예제처럼 BuildKit 컨테이너의 seccomp·AppArmor를 Unconfined로 사용하므로, 해당 실행을 허용하는 클러스터가 필요합니다. 이 Agent에서는 신뢰하는 소스만 빌드합니다.

설정값을 수정했다면 같은 integration Helm 명령으로 다시 적용합니다. 설정 재적용이 이미 성공한 빌드를 매번 다시 실행하지는 않습니다. CI 재실행은 Jenkins의 Build Now 또는 새 소스 push로 진행합니다.

## 관리

- 저장소별 GitLab 토큰은 기본 30일입니다. 자동 갱신 작업은 없습니다. 만료 하루 이내에 integration을 다시 적용하면 교체합니다. 초기 API 토큰도 유효해야 합니다.
- Registry 인증정보를 교체하면 values를 변경하고 integration을 다시 적용합니다. 저장소에 인증정보를 commit하지 않습니다.
- Argo CD 자동 동기화·self-heal은 켜고, Git에서 삭제한 리소스를 클러스터에서도 자동 삭제하는 prune은 끕니다. 기존 배포 저장소를 먼저 검토하려면 `argocd.automated: false`로 시작합니다.
- Helm uninstall은 API로 만든 GitLab 프로젝트·토큰·Webhook, Jenkins 작업·인증정보, Argo 리소스·다운로드 Secret을 자동 삭제하지 않습니다. 배포 네임스페이스도 유지합니다.
- 별도로 관리 중인 같은 이름의 작업·Webhook·Argo 리소스·Secret은 덮어쓰지 않고 실패하도록 구성합니다.

## 공식 자료

- [Jenkins GitLab 플러그인](https://plugins.jenkins.io/gitlab-plugin/)
- [GitLab Webhook 내부망 요청 제한](https://docs.gitlab.com/security/webhooks/)
- [Kubernetes 비공개 Registry 인증](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
- [BuildKit Kubernetes rootless 예제](https://github.com/moby/buildkit/blob/master/examples/kubernetes/job.rootless.yaml)
- [Argo CD 선언적 설정](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
