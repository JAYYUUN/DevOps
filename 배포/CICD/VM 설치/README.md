## GitLab 설치

GitLab은 별도 VM에 Linux 패키지로 설치합니다.
설치 방법은 [GitLab 공식 설치 문서](https://docs.gitlab.com/install/package/)에서 사용하는 OS에 맞는 안내를 따릅니다.

1. GitLab 패키지 저장소를 추가합니다.
- sudo apt update
- sudo apt install -y curl

GitLab 저장소를 추가하려면 다음 스크립트를 사용하십시오
curl --location "https://packages.gitlab.com/install/repositories/gitlab/gitlab-ee/script.deb.sh" | sudo bash

2. 패키지를 설치하세요
sudo EXTERNAL_URL="https://gitlab.example.com" apt install gitlab-ee

- `EXTERNAL_URL`에 실제로 GitLab에 접속할 주소를 입력합니다. `gitlab.example.com`은 예시이므로 서버 IP 또는 사용할 도메인으로 변경해야 합니다.
- `https://`의 경우: 기본적으로 Let’s Encrypt 인증서 자동 발급·적용을 시도합니다. 실제 공개 도메인의 DNS가 서버를 가리키고, 외부에서 서버의 TCP 80·443 포트에 접근할 수 있어야 합니다. 사설 IP는 자동 발급 대상이 아니며, 사설망에서 HTTPS를 사용하려면 자체 인증서 또는 사내 인증서를 별도로 구성해야 합니다.
- `http://`의 경우: 인증서 발급 없이 HTTP로 구성합니다. 도메인 없이 서버 IP로 설치할 수 있으며, 접속 트래픽은 암호화되지 않습니다.

## Jenkins 설치

Jenkins는 별도 VM에 설치합니다.
설치 방법은 [Jenkins 공식 Linux 설치 문서](https://www.jenkins.io/doc/book/installing/linux/)에서 사용하는 OS에 맞는 안내를 따릅니다.


