# Argo CD

GitLab의 Kubernetes YAML·Helm Chart를 읽고 클러스터 상태를 비교·동기화하는 독립 Helm 모듈입니다. GitLab·Jenkins의 Envoy Controller·Gateway·LB·인증서·Redis를 공유하지 않습니다.

## 구성

| 구성요소 | 역할·저장 위치 |
|---|---|
| API Server | 웹·CLI·API 제공 |
| Application Controller | Git의 배포 정의와 실제 클러스터 상태 비교·동기화 |
| Repo Server | Git 저장소 체크아웃과 Helm·Kustomize·YAML 변환. 기본 임시 공간 |
| 내부 Redis | Argo CD 전용 캐시. 외부 Redis·PVC 불필요 |
| 전용 Envoy Controller·Gateway·LB | `https://argocd.internal` 접속 입구 |
| TLS Secret | 자체 서명 CA·서버 인증서·개인키 자동 생성. 기존 Secret 재사용 |
| 저장소 Secret | 선택적으로 GitLab HTTPS 인증정보 등록 |

배포 원본은 GitLab에, Argo CD 설정·Application·인증정보는 Kubernetes 리소스(CR·ConfigMap·Secret)에 저장되어 etcd에 보관됩니다. 기본 구성은 PV·PVC·외부 DB를 만들지 않습니다. Repo Server 임시 디스크가 부족할 정도로 저장소가 커지면 별도 볼륨을 검토합니다.

Argo CD Chart 10.11.1 / Argo CD v3.5.6, Envoy Chart 1.9.2를 포함합니다. SSO(Dex)·Notifications는 끄고 ApplicationSet은 replicas 0으로 둡니다. ApplicationSet Deployment·Service는 존재할 수 있지만 실행 Pod는 없습니다. 단일 인스턴스 구성으로 HA는 아닙니다. 기본 실행 Pod는 Argo CD 핵심 4개와 Envoy Controller이며, 요청 처리용 Envoy Pod가 추가 생성됩니다.

## 입력 — values.yaml

초기 설치는 `gateway.serviceAnnotations`의 CHANGE_ME 키·값만 바꿉니다. 콘솔에서 발급받는 값이 아니라 CSP가 정의한 내부 LoadBalancer 설정입니다.

| 환경 | 입력할 키 | 입력할 값 |
|---|---|---|
| NHN NKS | `service.beta.kubernetes.io/openstack-internal-load-balancer` | `"true"` |
| AWS Load Balancer Controller | `service.beta.kubernetes.io/aws-load-balancer-scheme` | `"internal"` |
| Azure AKS | `service.beta.kubernetes.io/azure-load-balancer-internal` | `"true"` |
| Google GKE | `networking.gke.io/load-balancer-type` | `"Internal"` |

NHN 예시:

```yaml
gateway:
  serviceAnnotations:
    service.beta.kubernetes.io/openstack-internal-load-balancer: "true"
```

다른 CSP에서는 해당 키·값으로 교체합니다. 클라우드 Controller·버전에 따라 LB 클래스·서브넷·권한 등의 추가 설정이 필요할 수 있습니다. 필요하면 `templates/gateway.yaml`의 `envoyService`도 공식 API에 맞게 조정합니다. 빈 annotation은 내부망을 보장하지 않습니다. LB 생성에는 비용이 발생할 수 있습니다.

도메인을 바꾸려면 `argocd.global.domain`과 `argocd.server.httproute.hostnames`를 함께 변경합니다. 자원은 각 `resources`에서 변경합니다. 기본 Argo CD CPU 요청 합계는 350m·메모리 1152Mi이며 Envoy Controller(기본 100m·256Mi), Envoy Proxy, 초기화 Job 자원은 별도입니다. 제안 초기값이며 실제 부하를 측정해 조정합니다.

## 설치 전 준비

- Gateway API·Envoy CRD는 클러스터 공통 관리합니다. GitLab·Jenkins에서 이미 설치했다면 중복 설치하지 않고 Envoy 1.9.2와 호환되는지 확인합니다.
- Argo CD 전용 Application·AppProject·ApplicationSet CRD는 공식 Argo Chart가 생성하고 삭제 시 보존합니다. 다른 Argo CD가 이미 소유하면 설치·업그레이드 주체를 먼저 정합니다.
- 현재 클러스터는 CPU 여유가 적으므로 Argo CD·Envoy용 자원을 확보합니다. 이미지 다운로드를 위한 외부 통신도 필요합니다.

```bash
kubectl get crd gateways.gateway.networking.k8s.io httproutes.gateway.networking.k8s.io gatewayclasses.gateway.networking.k8s.io envoyproxies.gateway.envoyproxy.io
kubectl get deployment -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,IMAGE:.spec.template.spec.containers[*].image'
```

Gateway·Envoy CRD가 전혀 없는 새 클러스터에서만 공통 설치합니다. 기존 클러스터에 버전 확인 없이 적용하거나 기존 CRD의 Helm 소유권을 바꾸지 않습니다.

```bash
helm template gateway-crds oci://docker.io/envoyproxy/gateway-crds-helm --version v1.9.2 --set crds.gatewayAPI.enabled=true --set crds.envoyGateway.enabled=true | kubectl apply --server-side -f -
```

## 설치

`argocd` 폴더 상위에서 실행합니다. 공식 Chart는 `charts/`에 포함되어 있어 의존성 다운로드는 필요하지 않습니다.

```bash
helm lint ./argocd -f ./argocd/values.yaml
helm upgrade --install argocd ./argocd --namespace argocd --create-namespace -f ./argocd/values.yaml --skip-crds --wait --timeout 20m
kubectl get pods -n argocd
kubectl get gateway,httproute -n argocd
kubectl get svc -n argocd
```

`--skip-crds`는 Chart의 crds/ 설치를 건너뛰는 옵션입니다. Argo Chart가 templates로 생성하는 전용 CRD는 `argocd.crds.install: true`에 따라 설치됩니다. Gateway API 지원은 공식 Argo Chart에서 실험적 기능으로 표시되므로 실제 접속을 확인합니다.

## 접속

```bash
kubectl get gateway argocd-gateway -n argocd
```

ADDRESS를 아래 `<ARGOCD_LB_IP>`에 넣고 배스천에서 확인합니다.

```bash
curl -kI --connect-timeout 5 --resolve argocd.internal:443:<ARGOCD_LB_IP> https://argocd.internal/
```

PC가 사설 IP에 접근하지 못하면 PC PowerShell에서 SSH 터널을 엽니다. 키·배스천 주소·포트·LB IP는 실제 값으로 바꿉니다. GitLab/Jenkins 터널이 로컬 443·8443을 사용 중일 수 있어 Argo CD 예시는 9443을 사용합니다.

```powershell
ssh -o ExitOnForwardFailure=yes -i "C:\경로\접속키.pem" -p 22223 -N -L 127.0.0.1:9443:<ARGOCD_LB_IP>:443 ubuntu@배스천_주소
```

관리자 PowerShell에서 PC hosts에 추가합니다. 기존 항목이 있으면 중복 추가하지 않습니다.

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "`r`n127.0.0.1 argocd.internal"
ipconfig /flushdns
```

SSH 창을 열어두고 https://argocd.internal:9443 에 접속합니다. 이는 PC 접속용 터널이며 기준 도메인은 argocd.internal입니다. 향후 SSO 콜백 등은 기준 URL과 접속 포트를 일치시켜야 합니다. 내부망 직접 접속은 DNS를 LB 주소로 등록하고 기본 HTTPS 443을 사용합니다. LB IP는 배포 후 할당되며 values에 다시 넣지 않습니다.

ID `admin`, 최초 비밀번호는 배스천에서 확인합니다. 로그인 후 변경합니다.

```bash
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d; echo
```

CA 신뢰 등록에 사용할 공개 인증서를 추출합니다. 개인키는 복사하지 않습니다.

```bash
kubectl get secret argocd-gateway-tls -n argocd -o jsonpath='{.data.ca\.crt}' | base64 -d > argocd-ca.crt
```

자체 서명 CA를 PC·CLI 등 클라이언트에 신뢰 등록합니다. `curl -k`는 확인용입니다. CLI는 HTTPRoute를 통해 `argocd login argocd.internal:9443 --grpc-web` 방식으로 사용하며 인증서 신뢰가 필요합니다. 원시 gRPC용 GRPCRoute는 생성하지 않습니다.

## GitLab 저장소 연결 — 선택

설치만 할 때는 `repository.enabled: false`를 유지합니다. 연결할 때만 값을 입력합니다.

```yaml
repository:
  enabled: true
  url: https://gitlab.internal/그룹/배포저장소.git
  username: 실제_GitLab_접속계정
  token: 실제_저장소_읽기권한_토큰
```

| 입력 | 넣을 값 |
|---|---|
| `url` | GitLab 프로젝트의 HTTPS clone 주소. `.git` 포함 |
| `username` | 토큰 종류에 맞는 GitLab 사용자명 또는 Deploy Token 사용자명 |
| `token` | 해당 저장소를 읽을 수 있는 Personal/Project Access Token 또는 Deploy Token |

이 모듈은 제공받은 인증값을 repository Secret으로 등록합니다. GitLab에 계정·프로젝트·토큰을 새로 발급하지 않습니다. 비밀값이 들어간 values는 Git에 올리지 않으며 Helm release에도 저장됩니다.

Argo CD Pod에서도 `gitlab.internal`을 조회하고 GitLab LB의 HTTPS에 접근할 수 있어야 합니다. PC hosts·SSH 터널은 Pod DNS를 설정하지 않습니다. 내부 DNS 연결을 먼저 준비합니다.

현재 GitLab의 자체 서명 CA를 배스천에서 추출합니다.

```bash
kubectl get secret gitlab-wildcard-tls-ca -n gitlab -o jsonpath='{.data.cfssl_ca}' | base64 -d
```

실제 GitLab CA Secret 이름·키가 다르면 현재 Chart의 Secret을 확인합니다. 공개 CA PEM 내용을 기존 `values.yaml`의 `argocd.configs.tls.certificates`에 합쳐 넣습니다.

```yaml
argocd:
  configs:
    tls:
      certificates:
        gitlab.internal: |
          -----BEGIN CERTIFICATE-----
          실제_GitLab_CA_PEM_내용
          -----END CERTIFICATE-----
```

이는 Argo CD 웹 접속용 CA와 다른 **GitLab 서버 신뢰용 CA**입니다. 검증 우회는 기본으로 설정하지 않습니다. 수정 후 같은 Helm upgrade 명령으로 반영합니다.

등록만으로 자동 배포되지는 않습니다. `examples/application.yaml`의 저장소·브랜치·경로·대상 네임스페이스를 실제 값으로 바꿔 별도 적용합니다.

```bash
kubectl apply -f ./argocd/examples/application.yaml
```

예시는 수동 Sync이며 자동 동기화·자동 삭제는 켜지 않았습니다. 초기 연결 확인 후 자동화 정책을 정합니다. 배포 대상은 현재 클러스터이고 외부 클러스터 등록은 별도입니다.

## 보존·운영

- 영구 PVC는 없지만 설정·저장소 인증·Application·Secret을 포함한 Kubernetes 리소스와 etcd 백업이 필요합니다. 공식 Argo CD CLI의 `argocd admin export -n argocd > argocd-backup.yaml`로 내보낼 수 있습니다. 백업에는 인증정보가 포함될 수 있으므로 보호합니다.
- Helm 삭제 시 보존되는 Argo CD CRD와 Gateway TLS Secret만으로 전체 복구가 되는 것은 아닙니다. 나머지 Helm 관리 설정·인증정보는 삭제될 수 있습니다. 삭제 전 백업합니다.
- TLS는 최초 생성 후 Secret 재사용이며 자동 갱신하지 않습니다. 만료·도메인 변경은 접근 중단 시간을 잡고 기존 Secret 백업 → `argocd-gateway-tls` 삭제 → Helm upgrade → 새 CA 신뢰 등록 순서로 교체합니다.
- 같은 네임스페이스에는 이 모듈 하나를 설치합니다. 다른 Argo CD 모듈을 추가하면 Controller 식별자·CRD 관리 범위·Application 관리 범위도 따로 정해야 합니다.
- Gateway/Envoy CRD는 다른 모듈도 쓰므로 Jenkins·GitLab 삭제 시 공통 CRD까지 삭제하지 않도록 별도 관리합니다.
- GitLab 토큰 발급·DNS 등록·인증서 신뢰·Application 생성·자동 배포 정책은 자동화되지 않습니다. 실제 설치·HTTPS·저장소 연결·복구는 클러스터에서 검증해야 합니다.

## 공식 참조

[Argo CD 구조·저장소](https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/) · [Argo Helm Chart](https://github.com/argoproj/argo-helm/tree/argo-cd-10.11.1/charts/argo-cd) · [저장소 Secret](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/) · [Envoy 설치](https://gateway.envoyproxy.io/docs/install/install-helm/)

CSP 내부 LB: [NHN](https://docs.gov-nhncloud.com/ko/Container/NKS/ko/user-guide-gov/) · [AWS](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/service/annotations/) · [AKS](https://learn.microsoft.com/ko-kr/azure/aks/internal-lb) · [GKE](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/internal-load-balancing)
