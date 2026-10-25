# Jenkins

공식 Jenkins Chart와 전용 Envoy Gateway Controller를 설치합니다. GitLab의 Controller·Gateway·LB·인증서·볼륨을 공유하지 않습니다. Gateway API·Envoy CRD만 클러스터 공통으로 관리합니다.

## 구성

| 구성요소 | 역할 |
|---|---|
| Jenkins Controller | 웹·설정·인증정보·빌드 이력. `/var/jenkins_home`을 기존 블록 볼륨에 저장 |
| Kubernetes Agent | CI 실행 때 생성하는 작업용 Pod. 기본 작업 공간은 임시 저장소 |
| PV·PVC | Jenkins 전용 기존 볼륨 연결. 기본 20Gi·RWO·Retain |
| 전용 Envoy Controller | `gateway.envoyproxy.io/jenkins-controller`로 Jenkins Gateway만 관리 |
| GatewayClass·Gateway·EnvoyProxy | Jenkins 전용 LB와 HTTPS 입구 구성 |
| HTTPRoute | 공식 Jenkins Chart가 `jenkins.internal` 요청을 Jenkins Service로 연결 |
| TLS Secret | Helm이 자체 서명 CA·서버 인증서·개인키 생성. 기존 Secret 재사용 |

Jenkins Chart 5.9.73 / Jenkins 2.580.1, Envoy Gateway Chart 1.9.2를 포함합니다. 공식 Chart 원본은 `charts/`에 포함되어 있어 의존성 다운로드 없이 설치합니다. 이미지·플러그인 다운로드는 별도로 외부 통신이 필요합니다.

## 입력 — values.yaml

volume은 Jenkins 본체의 데이터를 보관할 디스크 연결 설정이다. Jenkins 설정·플러그인·인증정보·작업 정의·빌드 이력·로그를 저장한다.
필수 입력은 `CHANGE_ME` 세 개입니다.

| 항목 | 넣을 값·확인 방법 |
|---|---|
| `volume.driver` | 설치된 CSI 이름. AWS EBS `ebs.csi.aws.com`. `kubectl get csidriver`로 확인 |
| `volume.volumeHandle` | 미리 만든 Jenkins 전용 볼륨 ID. UUID, AWS EBS `vol-...`. |
| `volume.zone` | 실제 볼륨 가용 영역. kubectl get nodes -L topology.kubernetes.io/zone에서 확인, `KR1` 같은 리전 이름 아님 |
| `volume.size` | 기본 `20Gi`. 실제 볼륨 크기 이하. 디스크를 생성·확장하지 않음 |
| `volume.fsType` | 기본 `ext4`. 기존 XFS 볼륨만 `xfs`. 다른 형식으로 자동 변환하지 않음 |
| `gateway.serviceAnnotations` | LB 생성 방식. 현재 NHN 내부망용 기본값. 다른 CSP는 내부 LB annotation으로 교체 |

```bash
kubectl get csidriver
kubectl get nodes -L topology.kubernetes.io/zone
```

기본 도메인은 `jenkins.internal`입니다. 바꾸려면 `jenkins.controller.jenkinsUrl`과 `jenkins.controller.httpRoute.hostnames`를 함께 변경합니다. 특정 노드는 지정하지 않고 볼륨과 같은 AZ에서 배치합니다. CSI가 다른 topology 키를 사용하면 `templates/storage.yaml`을 조정합니다.

NHN 내부 LB 기본값은 아래와 같습니다. 플로팅 IP 없이 사설 VIP를 생성합니다.

```yaml
gateway:
  serviceAnnotations:
    service.beta.kubernetes.io/openstack-internal-load-balancer: "true"
```

다른 클라우드에서는 이 항목을 그 클라우드의 내부 LB 설정으로 **교체**합니다. AWS의 LB Controller 종류와 설정 등은 별도 확인이 필요합니다. 빈 annotation은 내부 전용을 보장하지 않습니다. LB 생성에는 클라우드 비용이 발생할 수 있습니다.

## 준비

- 20Gi 이상 Jenkins 전용 블록 볼륨과 CSI 드라이버. 빈 볼륨은 CSI가 포맷할 수 있으므로 기존 데이터·파일시스템을 먼저 확인합니다.
- Gateway API·Envoy 공통 CRD. 현재 GitLab에서 사용 중인 CRD가 있으므로 중복 설치하지 않습니다. 두 Controller가 사용할 공통 CRD는 Envoy 1.9.2와 호환되어야 합니다.
- Controller·Envoy·빌드 Agent를 배치할 자원. 현재 클러스터 CPU 여유가 적으므로 증설 또는 기존 자원 조정이 필요할 수 있습니다.

```bash
kubectl get crd gateways.gateway.networking.k8s.io httproutes.gateway.networking.k8s.io gatewayclasses.gateway.networking.k8s.io envoyproxies.gateway.envoyproxy.io
kubectl get deployment -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,IMAGE:.spec.template.spec.containers[*].image'
```

새 클러스터에 CRD가 아예 없을 때만 공식 CRD Chart로 공통 설치합니다. 기존 클러스터에 버전 확인 없이 적용하지 않습니다.

```bash
helm template gateway-crds oci://docker.io/envoyproxy/gateway-crds-helm --version v1.9.2 --set crds.gatewayAPI.enabled=true --set crds.envoyGateway.enabled=true | kubectl apply --server-side -f -
```

CRD는 Jenkins 릴리스에 속하지 않습니다. GitLab이 소유한 기존 CRD의 Helm 소유권을 바꾸거나 GitLab 삭제 시 CRD까지 삭제하면 다른 Gateway에도 영향이 있습니다. 공통 CRD의 업그레이드·삭제는 별도 관리합니다.

## 설치

`jenkins` 폴더의 상위 디렉터리에서 실행합니다.

```bash
helm lint ./jenkins -f ./jenkins/values.yaml
helm upgrade --install jenkins ./jenkins --namespace jenkins --create-namespace -f ./jenkins/values.yaml --skip-crds --wait --timeout 20m
kubectl get pods,pvc -n jenkins
kubectl get gateway,httproute -n jenkins
kubectl get svc -n jenkins
```

Controller·PVC·Gateway는 같은 `jenkins` 네임스페이스에 생성됩니다. GatewayClass 이름은 네임스페이스·릴리스 이름으로 생성합니다. 이 모듈은 네임스페이스당 Jenkins 하나를 전제로 합니다. 다른 Jenkins 모듈을 추가하면 `envoy-gateway.config.envoyGateway.gateway.controllerName`도 고유하게 바꿉니다.

## 접속

Jenkins LB 주소는 배포 후 할당됩니다. GitLab LB IP를 사용하지 않습니다.

```bash
kubectl get gateway jenkins-gateway -n jenkins
```

배스천에서 `<JENKINS_LB_IP>`를 위 `ADDRESS`로 바꿔 확인합니다.

```bash
curl -kI --connect-timeout 5 --resolve jenkins.internal:443:<JENKINS_LB_IP> https://jenkins.internal/login
```

PC가 사설망에 직접 접근하지 못하면 PC PowerShell에서 SSH 터널을 엽니다. 키·포트·배스천·Jenkins LB IP는 실제 값으로 변경합니다. GitLab 터널이 PC 443 포트를 사용하므로 Jenkins는 PC 8443을 사용합니다.

```powershell
ssh -o ExitOnForwardFailure=yes -i "C:\경로\접속키.pem" -p 22223 -N -L 127.0.0.1:8443:<JENKINS_LB_IP>:443 ubuntu@배스천_주소
```

관리자 PowerShell에서 hosts 항목을 추가합니다. 이미 있으면 중복 추가하지 않습니다.

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "`r`n127.0.0.1 jenkins.internal"
ipconfig /flushdns
```

SSH 창을 열어둔 상태에서 https://jenkins.internal:8443 로 접속합니다. 이는 PC 접속용 터널 주소이고 Jenkins의 기준 URL은 https://jenkins.internal 입니다. 일부 기능이 기준 URL로 이동하면 8443 터널과 맞지 않을 수 있습니다. 주소를 완전히 일치시키려면 기존 GitLab 터널의 443 점유를 해제한 뒤 Jenkins 터널도 로컬 443으로 연결합니다. 클러스터 안의 GitLab·Agent용 DNS는 PC hosts와 별도입니다.

ID는 `admin`, 비밀번호는 배스천에서 확인합니다.

```bash
kubectl get secret jenkins -n jenkins -o jsonpath='{.data.jenkins-admin-password}' | base64 -d; echo
```

자체 서명 CA를 신뢰 등록하려면 공개 CA만 추출합니다.

```bash
kubectl get secret jenkins-gateway-tls -n jenkins -o jsonpath='{.data.ca\.crt}' | base64 -d > jenkins-ca.crt
```

이 CA를 PC·GitLab Webhook 등 HTTPS 클라이언트의 신뢰 저장소에 등록합니다. 개인키는 복사하지 않습니다. `curl -k`는 접속 확인용이며 신뢰 등록을 대체하지 않습니다.

## 변경·보존

- Controller·Agent 자원은 `jenkins.controller.resources`, `jenkins.agent.resources`로 변경합니다. 제안 기본값은 Controller 100m·1Gi, Agent당 250m·512Mi 요청입니다. Envoy Controller는 공식 기본값 100m·256Mi를 사용하며 요청 처리용 Envoy 자원도 별도로 필요합니다. 실제 사용량을 측정해 조정합니다.
- Controller에서는 CI를 실행하지 않습니다. GitLab 코드·Jenkinsfile을 Agent가 내려받아 빌드합니다. GitLab DNS·CA 신뢰·인증정보·Webhook·이미지 빌드 도구 설정은 이후 연동 작업입니다. 이 모듈은 그 연동을 자동 등록하지 않습니다.
- PV·PVC·TLS Secret은 Helm 삭제 시 보존합니다. 원본 볼륨은 Retain입니다. 보존은 백업이 아니며 Jenkins Home 전체 백업과 복구 검증이 필요합니다. 빌드 이력 보관 수를 제한합니다.
- 재설치는 같은 네임스페이스·릴리스 이름을 사용합니다. 볼륨 ID·AZ·파일시스템 변경은 사용 중 PV에서 단순 업그레이드하지 말고 Controller 중지·보존·재연결 절차로 진행합니다.
- 인증서는 최초 생성 후 재사용하며 자동 갱신하지 않습니다. 만료·도메인 변경 시 Jenkins 접근 중단 시간을 잡고 기존 인증서를 백업한 뒤 `jenkins-gateway-tls` Secret을 삭제하고 Helm upgrade로 재생성합니다. CA도 바뀌므로 클라이언트 신뢰를 다시 등록합니다.
- 실제 마운트 권한·Pod 재생성 후 데이터 유지·내부 LB·백업은 실제 클러스터에서 검증합니다. 설치 중 certgen·Jenkins 초기화 같은 일회성 Job은 Completed가 정상입니다. Jenkins는 단일 Controller로 자동 HA 구성이 아닙니다.

## 공식 참조

- [Jenkins Kubernetes 설치](https://www.jenkins.io/doc/book/installing/kubernetes/)
- [Jenkins 공식 Chart](https://github.com/jenkinsci/helm-charts/tree/jenkins-5.9.73/charts/jenkins)
- [Envoy Helm 설치](https://gateway.envoyproxy.io/docs/install/install-helm/)
- [Envoy 다중 Controller](https://gateway.envoyproxy.io/docs/tasks/operations/deployment-mode/)
- [NHN NKS 내부 LB](https://docs.gov-nhncloud.com/ko/Container/NKS/ko/user-guide-gov/)
