# Git 환경 설정 및 서버로 모듈 가져오기

이 문서는 GitHub에 보관한 **Kubernetes Observability 재사용 모듈을 Bastion/관리 서버로 가져오고 업데이트하는 방법**을 설명합니다. `git/` 폴더는 Git 사용 가이드만 보관하며, Git 저장소 자체를 중첩 생성하거나 Kubernetes에 리소스를 배포하지 않습니다.

## 1. Git이란? 왜 필요한가?

Git은 파일 변경 이력을 관리하는 버전 관리 도구이고, GitHub는 Git 저장소를 원격으로 보관하는 서비스입니다. GitHub에서 모듈을 내려받아 두면 서버에서 설정 파일을 일일이 복사하지 않아도 되고, 이후 수정사항도 `git pull`로 반영할 수 있습니다.

아래 예시는 Ubuntu Bastion에서 실행합니다. 실제 GitHub 저장소는 `https://github.com/JAYYUUN/DevOps.git`이고, 저장소 내부의 모듈 경로는 **GitHub에 올린 실제 폴더 위치**에 맞춰야 합니다.

## 2. 서버에 Git 설치 및 확인

먼저 서버에 Git 명령어가 있는지 확인합니다. Git이 없다면 Ubuntu의 패키지 관리자를 통해 설치합니다. 설치 후 버전을 확인하면 다음 단계로 진행할 수 있습니다.

```bash
git --version
# 설치되지 않은 경우에만
sudo apt-get update
sudo apt-get install -y git
git --version
```

## 3. Git 파일을 둘 디렉터리 만들기

Kubernetes 배포 파일과 다른 작업 파일이 뒤섞이지 않도록 홈 디렉터리에 `~/git`을 만듭니다. 이 경로는 예시이므로 `/opt/git` 등 권한이 있는 다른 위치를 사용해도 됩니다.

```bash
mkdir -p ~/git
cd ~/git
pwd
```

## 4. GitHub 저장소 가져오기 (전체 저장소)

`git clone`은 GitHub 원격 저장소의 파일과 변경 이력을 서버로 복사합니다. 최초 한 번만 실행하며, 이후에는 `git pull`로 변경사항을 가져옵니다.

```bash
cd ~/git
git clone https://github.com/JAYYUUN/DevOps.git
cd ~/git/DevOps
ls -la
```

모듈 폴더가 저장소 최상위에 올라갔다면 아래와 같이 이동합니다. 실제 업로드한 폴더 이름이 다르다면 GitHub의 경로에 맞게 변경하세요.

```bash
cd ~/git/DevOps/k8s-observability-reusable
ls -la
cat README.md
```

> `git clone`은 **Git 저장소 전체**를 가져옵니다. 모듈 폴더에 별도로 `git init`을 실행할 필요가 없습니다.

## 5. 필요한 폴더만 가져오기 (sparse-checkout)

저장소에 여러 운영 모듈이 들어 있다면 `sparse-checkout`을 사용해 필요한 폴더만 작업 디렉터리에 표시할 수 있습니다. 아래 명령은 **4번 전체 clone 대신** 선택해서 사용하는 방법입니다. 원격 저장소의 모듈 경로가 다르면 `git sparse-checkout set`의 인자를 변경하세요.

# 1. ~/git 폴더를 만들고 이동
mkdir -p ~/git
cd ~/git

# 2. DevOps-sparse 폴더에 Git 관리 정보와 저장소 루트 파일을 내려받음
#    k8s-observability-reusable 폴더의 파일은 아직 내려받지 않음
git clone --filter=blob:none --sparse https://github.com/JAYYUUN/DevOps.git DevOps-sparse

# 3. 생성된 DevOps-sparse 폴더로 이동
cd DevOps-sparse

# 4. k8s-observability-reusable 폴더와 그 안의 파일을 내려받음
git sparse-checkout set k8s-observability-reusable

# 5. 내려받은 폴더로 이동하여 파일 목록 확인
cd k8s-observability-reusable
ls -la
서버의 Git 버전이나 원격 서버의 부분 다운로드 지원 여부에 따라 `--filter`가 지원되지 않을 수 있습니다. 그 경우 `--filter=blob:none` 옵션만 빼고 실행하면 됩니다.

## 6. GitHub 변경사항 가져오기

GitHub에서 README, values, `.conf` 등을 수정한 뒤 서버에서 `git pull`을 실행하면 최신 변경사항을 가져옵니다. `git pull`은 로컬에서 수정한 파일과 충돌할 수 있으므로 먼저 `git status`를 확인하세요.

```bash
cd ~/git/DevOps
git status
git pull --ff-only
```

`sparse-checkout`을 사용했다면 `~/git/DevOps-sparse`에서 같은 명령을 실행합니다. 서버에서 직접 수정한 파일이 있다면 커밋 또는 백업한 후 업데이트하세요.

## 7. 비공개 저장소일 때 인증

GitHub 저장소가 Private이면 HTTPS clone/pull 과정에서 인증이 필요합니다. GitHub 계정 비밀번호 대신 개인 액세스 토큰(PAT)이나 SSH 키를 사용하며, **토큰을 명령어 URL에 직접 넣거나 README에 저장하지 않습니다.**

SSH 방식은 서버에서 키를 생성하고 GitHub 계정의 SSH 키에 공개키를 등록한 후 사용합니다. 공개키만 GitHub에 등록하고 개인키는 서버 밖으로 공유하지 마세요.

```bash
ssh-keygen -t ed25519 -C "bastion-github" -f ~/.ssh/id_ed25519_github
cat ~/.ssh/id_ed25519_github.pub
```

GitHub 웹 화면의 **Settings → SSH and GPG keys → New SSH key**에 출력된 공개키를 등록합니다. 이후 SSH 접속을 시험하고 SSH 주소로 clone할 수 있습니다.

```bash
ssh -T git@github.com
git clone git@github.com:JAYYUUN/DevOps.git
```

## 8. 서버에서 GitHub 접속이 차단된 경우

폐쇄망이나 방화벽 때문에 Bastion에서 GitHub에 접속할 수 없다면 인터넷이 되는 PC에서 저장소 ZIP을 받은 뒤 `scp`로 서버에 복사합니다. 이 방식으로 받은 ZIP에는 일반적으로 Git 변경 이력이 포함되지 않으므로 `git pull`을 사용하려면 별도로 clone해야 합니다.

Windows PowerShell 예시(PC에서 실행):

```powershell
scp -i "C:\path\to\bastion-key.pem" "C:\path\to\DevOps.zip" ubuntu@BASTION_IP:/home/ubuntu/git/
```

Bastion에서 압축 해제:

```bash
mkdir -p ~/git
cd ~/git
unzip DevOps.zip
```

서버에 `~/git`이 없으면 SCP 전송 전에 서버에서 3번 명령으로 먼저 생성하세요. SSH 포트가 기본값 22가 아니라면 SCP에 `-P 포트번호`를 추가합니다.

## 9. 내려받은 모듈 실행

GitHub에서 파일을 가져오는 과정은 배포가 아닙니다. 저장소의 모듈 디렉터리로 이동한 뒤 각 모듈 README를 읽고 필요한 Helm 차트만 설치합니다. Loki는 설치 전에 별도 인증정보 파일을 준비해야 합니다.

```bash
cd ~/git/DevOps/k8s-observability-reusable
cat prometheus/README.md
cat loki/README.md
cat fluentd/README.md

# 필요한 모듈만 선택해서 설치
bash scripts/install-module.sh prometheus
# Loki 인증정보 준비 후
bash scripts/install-module.sh loki
bash scripts/install-module.sh fluentd
```

설치 스크립트 상세 사용법은 [`../scripts/README.md`](../scripts/README.md)를 참고하세요.
