"""기존 도구의 API만 사용해 연동합니다. 설치 Chart 파일은 변경하지 않습니다."""
import base64
import datetime as dt
import http.cookiejar
import json
import os
import secrets
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

OWNER_LABEL = "cicd-integration-owner"

class ApiError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"HTTP {status}")

class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (old.scheme, old.netloc) != (new.scheme, new.netloc):
            raise RuntimeError("다른 주소로의 리다이렉트를 차단했습니다. 서비스 URL을 확인하세요")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Http:
    def __init__(self, context=None):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            SameOriginRedirect(), urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=context or ssl.create_default_context()))

    def request(self, method, url, data=None, headers=None, form=False, raw=False):
        headers = dict(headers or {})
        body = None
        if data is not None:
            if form:
                body = urllib.parse.urlencode(data).encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                body = json.dumps(data).encode()
                headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as response:
                result = response.read().decode()
        except urllib.error.HTTPError as error:
            # 응답 본문·인증값·토큰을 로그에 출력하지 않습니다.
            raise ApiError(error.code) from None
        return result if raw else (json.loads(result) if result else {})

class Kube:
    def __init__(self):
        sa = Path("/var/run/secrets/kubernetes.io/serviceaccount")
        self.token = (sa / "token").read_text().strip()
        self.http = Http(ssl.create_default_context(cafile=str(sa / "ca.crt")))
        self.url = "https://kubernetes.default.svc"

    def call(self, method, path, data=None):
        return self.http.request(method, self.url + path, data,
                                 {"Authorization": "Bearer " + self.token})

    def get(self, path):
        try:
            return self.call("GET", path)
        except ApiError as error:
            if error.status == 404:
                return None
            raise

    def upsert(self, collection, obj, owner):
        path = collection + "/" + obj["metadata"]["name"]
        existing = self.get(path)
        obj["metadata"].setdefault("labels", {})[OWNER_LABEL] = owner
        if existing:
            if existing["metadata"].get("labels", {}).get(OWNER_LABEL) != owner:
                raise RuntimeError("동일 이름의 비관리 리소스가 있습니다. 이름을 바꾸세요: " + obj["metadata"]["name"])
            obj["metadata"]["resourceVersion"] = existing["metadata"]["resourceVersion"]
            return self.call("PUT", path, obj)
        return self.call("POST", collection, obj)

def core(ns, kind):
    return f"/api/v1/namespaces/{ns}/{kind}"

def argo(ns, kind):
    return f"/apis/argoproj.io/v1alpha1/namespaces/{ns}/{kind}"

def decode(data, key):
    return base64.b64decode(data[key]).decode()

class Bootstrap:
    def __init__(self, config, kube, http, token, config_dir):
        self.cfg, self.kube, self.http = config, kube, http
        self.token, self.config_dir = token, Path(config_dir)
        self.api = config["gitlab"]["url"].rstrip("/") + "/api/v4"
        self.state = {}

    def gl(self, method, path, data=None):
        return self.http.request(method, self.api + path, data, {"PRIVATE-TOKEN": self.token})

    def load_state(self):
        c = self.cfg
        existing = self.kube.get(core(c["namespace"], "secrets") + "/" + c["stateSecret"])
        if existing:
            if existing["metadata"].get("labels", {}).get(OWNER_LABEL) != c["owner"]:
                raise RuntimeError("다른 릴리스가 소유한 연동 상태 Secret입니다")
            self.state = json.loads(decode(existing["data"], "state.json"))
        else:
            self.save_state()

    def save_state(self):
        c = self.cfg
        obj = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": c["stateSecret"]},
               "type": "Opaque", "data": {"state.json": base64.b64encode(json.dumps(self.state).encode()).decode()}}
        self.kube.upsert(core(c["namespace"], "secrets"), obj, c["owner"])

    def wait_gitlab(self):
        deadline = time.monotonic() + self.cfg["bootstrap"]["waitSeconds"]
        while True:
            try:
                self.gl("GET", "/user")
                return
            except ApiError as error:
                if error.status in (401, 403):
                    raise RuntimeError("GitLab API 토큰의 api 범위와 권한을 확인하세요") from None
                if time.monotonic() >= deadline:
                    raise RuntimeError("GitLab API 준비 대기 시간이 초과됐습니다") from None
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("GitLab 내부 Service 연결을 확인하세요") from None
            time.sleep(5)

    def project(self, full_path, branch):
        encoded = urllib.parse.quote(full_path, safe="")
        try:
            return self.gl("GET", "/projects/" + encoded)
        except ApiError as error:
            if error.status != 404:
                raise
        if not self.cfg["gitlab"]["createProjectsIfMissing"]:
            raise RuntimeError("GitLab 프로젝트가 없습니다: " + full_path)
        parent, name = full_path.rsplit("/", 1)
        namespace = None
        for page in range(1, 6):
            query = urllib.parse.urlencode({"search": parent.rsplit("/", 1)[-1], "per_page": 100, "page": page})
            rows = self.gl("GET", "/namespaces?" + query)
            namespace = next((x for x in rows if x["full_path"] == parent), None)
            if namespace or len(rows) < 100:
                break
        if not namespace:
            raise RuntimeError("프로젝트를 만들 GitLab namespace가 없거나 접근할 수 없습니다: " + parent)
        return self.gl("POST", "/projects", {"name": name, "path": name, "namespace_id": namespace["id"],
                                              "visibility": "private", "initialize_with_readme": False})

    def repo_token(self, key, project_id, scopes, level):
        old = self.state.get(key)
        today = dt.date.today()
        if old:
            if old["project_id"] != project_id:
                raise RuntimeError("기존 연동의 프로젝트가 변경됐습니다. 별도 integration 릴리스를 사용하세요")
            if dt.date.fromisoformat(old["expires_at"]) > today + dt.timedelta(days=1):
                return old
        expires = (today + dt.timedelta(days=int(self.cfg["gitlab"]["tokenLifetimeDays"]))).isoformat()
        item = self.gl("POST", f"/projects/{project_id}/access_tokens", {
            "name": self.cfg["owner"] + "-" + key, "scopes": scopes,
            "access_level": level, "expires_at": expires})
        result = {"project_id": project_id, "id": item["id"], "username": "oauth2",
                  "token": item["token"], "expires_at": expires}
        self.state[key] = result
        self.save_state()
        return result

    def seed(self, source, deployment):
        if not self.cfg["demo"]["seedEmptyRepositories"]:
            return
        if source.get("empty_repo"):
            names = {self.cfg["source"]["pipelineFile"]: "Jenkinsfile",
                     "app.py": "app.py", "test_app.py": "test_app.py", "publish.py": "publish.py", "Dockerfile": "Dockerfile"}
            actions = [{"action": "create", "file_path": p,
                        "content": (self.config_dir / file).read_text()} for p, file in names.items()]
            self.gl("POST", f"/projects/{source['id']}/repository/commits", {
                "branch": self.cfg["source"]["branch"], "commit_message": "Add CI integration example", "actions": actions})
            print("빈 소스 저장소에 CI 예제를 생성했습니다", flush=True)
        if deployment.get("empty_repo"):
            actions = []
            for filename in ("kustomization.yaml", "deployment.yaml"):
                text = (self.config_dir / filename).read_text()
                actions.append({"action": "create", "file_path": self.cfg["deployment"]["path"].rstrip("/") + "/" + filename,
                                "content": text.replace("__PULL_SECRET__", self.cfg["pullSecret"])})
            self.gl("POST", f"/projects/{deployment['id']}/repository/commits", {
                "branch": self.cfg["deployment"]["branch"], "commit_message": "Add image deployment example", "actions": actions})
            print("빈 배포 저장소에 Kustomize Deployment 예제를 생성했습니다", flush=True)

    def verify_pipeline(self, project_id):
        q = urllib.parse.urlencode({"ref": self.cfg["source"]["branch"]})
        p = urllib.parse.quote(self.cfg["source"]["pipelineFile"], safe="")
        self.gl("GET", f"/projects/{project_id}/repository/files/{p}?{q}")

    def configure_jenkins(self, source, deployment, source_token, deploy_token):
        c = self.cfg
        secret = self.kube.get(core(c["jenkins"]["namespace"], "secrets") + "/" + c["jenkins"]["adminSecret"])
        if not secret:
            raise RuntimeError("Jenkins 관리자 Secret이 없습니다")
        username = decode(secret["data"], c["jenkins"]["userKey"])
        password = decode(secret["data"], c["jenkins"]["passwordKey"])
        auth = {"Authorization": "Basic " + base64.b64encode((username + ":" + password).encode()).decode()}
        base = c["jenkins"]["url"].rstrip("/")
        # 비밀번호 인증은 crumb와 같은 HTTP 세션 쿠키를 함께 사용합니다.
        deadline = time.monotonic() + c["bootstrap"]["waitSeconds"]
        while True:
            try:
                crumb = self.http.request("GET", base + "/crumbIssuer/api/json", headers=auth)
                break
            except (ApiError, urllib.error.URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Jenkins 준비·관리자 인증·CSRF crumb 설정을 확인하세요") from None
                time.sleep(5)
        headers = dict(auth)
        headers[crumb["crumbRequestField"]] = crumb["crumb"]
        owner_prefix = "cicd-" + c["owner"].replace(".", "-")
        data = {"owner": c["owner"], "job": c["jenkins"]["jobName"], "webhookEnabled": c["jenkins"]["webhook"]["enabled"],
                "webhookSecret": self.state["webhookSecret"],
                "sourceUrl": self.repo_url(c["source"]["project"]), "branch": c["source"]["branch"],
                "pipelineFile": c["source"]["pipelineFile"], "sourceCredentialId": owner_prefix + "-source",
                "deploymentCredentialId": owner_prefix + "-gitops", "sourceUser": source_token["username"],
                "sourceToken": source_token["token"], "deploymentToken": deploy_token["token"],
                "api": self.api, "sourceProjectId": source["id"], "deploymentProjectId": deployment["id"],
                "deploymentBranch": c["deployment"]["branch"], "manifestPath": c["deployment"]["path"].rstrip("/") + "/kustomization.yaml",
                "registryAddress": c["registry"]["address"], "registryRepository": c["registry"]["repository"],
                "registryCredentialId": owner_prefix + "-registry",
                "registryUser": os.environ["REGISTRY_PUSH_USER"], "registryPassword": os.environ["REGISTRY_PUSH_PASSWORD"],
                "buildContext": c["build"]["context"], "dockerfile": c["build"]["dockerfile"],
                "testCommand": c["build"]["testCommand"]}
        encoded = base64.b64encode(json.dumps(data).encode()).decode()
        script = (self.config_dir / "configure.groovy").read_text().replace("__CICD_DATA__", encoded)
        result = self.http.request("POST", base + "/scriptText", {"script": script}, headers, form=True, raw=True)
        if "CICD_SETUP_OK" not in result:
            raise RuntimeError("Jenkins 연동 구성에 실패했습니다. 플러그인·동일 이름 작업 충돌 여부를 확인하세요")
        if c["jenkins"]["runInitialBuild"] and not self.state.get("initialBuildQueued"):
            self.http.request("POST", base + "/job/" + urllib.parse.quote(c["jenkins"]["jobName"], safe="") + "/buildWithParameters", headers=headers, raw=True)
            self.state["initialBuildQueued"] = True
            self.save_state()
        print("Jenkins 저장소·Registry 인증·Pipeline·Webhook 수신을 구성했습니다", flush=True)

    def configure_registry(self):
        c = self.cfg; ns = c["deployment"]["namespace"]
        user, password = os.environ["REGISTRY_PULL_USER"], os.environ["REGISTRY_PULL_PASSWORD"]
        auth = base64.b64encode((user + ":" + password).encode()).decode()
        docker = {"auths": {c["registry"]["address"]: {"username": user, "password": password, "auth": auth}}}
        obj = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": c["pullSecret"]},
               "type": "kubernetes.io/dockerconfigjson", "data": {
                   ".dockerconfigjson": base64.b64encode(json.dumps(docker).encode()).decode()}}
        self.kube.upsert(core(ns, "secrets"), obj, c["owner"])

    def prepare_webhook(self):
        if "webhookSecret" not in self.state:
            self.state["webhookSecret"] = secrets.token_hex(32)
            self.save_state()
        c = self.cfg
        if not c["jenkins"]["webhook"]["enabled"]:
            return
        if c["gitlab"]["configureWebhookAllowlist"]:
            try:
                settings = self.gl("GET", "/application/settings")
                host = urllib.parse.urlsplit(c["jenkins"]["url"]).hostname
                allowed = settings.get("outbound_local_requests_whitelist") or []
                if host not in allowed:
                    self.gl("PUT", "/application/settings", {"outbound_local_requests_whitelist": allowed + [host]})
            except ApiError as error:
                if error.status in (401, 403):
                    raise RuntimeError("Webhook 내부 주소 허용에는 관리자 api 토큰이 필요합니다. 수동 허용했다면 gitlab.configureWebhookAllowlist=false로 설정하세요") from None
                raise

    def configure_webhook(self, project_id):
        c = self.cfg
        if not c["jenkins"]["webhook"]["enabled"]:
            return
        url = c["jenkins"]["url"].rstrip("/") + "/project/" + c["jenkins"]["jobName"]
        hooks = []
        page = 1
        while True:
            batch = self.gl("GET", f"/projects/{project_id}/hooks?per_page=100&page={page}")
            hooks.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        saved = self.state.get("webhookId")
        old = next((h for h in hooks if h["id"] == saved), None)
        if old and old["url"] != url:
            raise RuntimeError("기존 관리 Webhook URL이 바뀌었습니다. 기존 Hook을 확인하고 별도 릴리스를 사용하세요")
        if not old and any(h["url"] == url for h in hooks):
            raise RuntimeError("같은 URL의 비관리 Webhook이 있습니다. 기존 Hook을 확인하세요")
        payload = {"url": url, "token": self.state["webhookSecret"], "push_events": True,
                   "push_events_branch_filter": c["source"]["branch"], "merge_requests_events": False,
                   "tag_push_events": False, "enable_ssl_verification": True}
        path = f"/projects/{project_id}/hooks"
        if old:
            result = self.gl("PUT", path + "/" + str(old["id"]), payload)
        else:
            result = self.gl("POST", path, payload)
        self.state["webhookId"] = result["id"]
        self.save_state()
        print("GitLab Push Webhook을 등록했습니다", flush=True)

    def repo_url(self, project_path):
        return self.cfg["gitlab"]["url"].rstrip("/") + "/" + project_path + ".git"

    def configure_argocd(self, deploy_read):
        c = self.cfg; ns = c["argocd"]["namespace"]; name = c["argocd"]["applicationName"]
        url = self.repo_url(c["deployment"]["project"])
        repo = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": name + "-repository",
                "labels": {"argocd.argoproj.io/secret-type": "repository", "app.kubernetes.io/part-of": "argocd"}},
                "type": "Opaque", "stringData": {"type": "git", "url": url,
                "username": deploy_read["username"], "password": deploy_read["token"]}}
        self.kube.upsert(core(ns, "secrets"), repo, c["owner"])
        project = {"apiVersion": "argoproj.io/v1alpha1", "kind": "AppProject", "metadata": {"name": name},
                   "spec": {"sourceRepos": [url], "destinations": [{"server": "https://kubernetes.default.svc",
                   "namespace": c["deployment"]["namespace"]}], "clusterResourceWhitelist": [{"group": "", "kind": "Namespace"}],
                   "namespaceResourceWhitelist": [{"group": "*", "kind": "*"}]}}
        self.kube.upsert(argo(ns, "appprojects"), project, c["owner"])
        policy = {"syncOptions": ["CreateNamespace=true"]}
        if c["argocd"]["automated"]:
            policy["automated"] = {"prune": c["argocd"]["prune"], "selfHeal": c["argocd"]["selfHeal"]}
        app = {"apiVersion": "argoproj.io/v1alpha1", "kind": "Application", "metadata": {"name": name},
               "spec": {"project": name, "source": {"repoURL": url, "targetRevision": c["deployment"]["branch"],
               "path": c["deployment"]["path"]}, "destination": {"server": "https://kubernetes.default.svc",
               "namespace": c["deployment"]["namespace"]}, "syncPolicy": policy}}
        self.kube.upsert(argo(ns, "applications"), app, c["owner"])
        print("Argo CD 읽기 전용 저장소·전용 Project·Application을 구성했습니다", flush=True)

    def run(self):
        self.load_state(); self.wait_gitlab()
        source = self.project(self.cfg["source"]["project"], self.cfg["source"]["branch"])
        deployment = self.project(self.cfg["deployment"]["project"], self.cfg["deployment"]["branch"])
        self.prepare_webhook()
        self.seed(source, deployment); self.verify_pipeline(source["id"])
        read = self.repo_token("source-read", source["id"], ["read_repository", "read_api"], 20)
        write = self.repo_token("gitops-write", deployment["id"], ["api", "write_repository"], 40)
        argo_read = self.repo_token("gitops-read", deployment["id"], ["read_repository"], 20)
        self.configure_registry()
        self.configure_argocd(argo_read)
        self.configure_jenkins(source, deployment, read, write)
        self.configure_webhook(source["id"])
        print("CICD 연동 설정 완료. 빌드·동기화 결과는 Jenkins·Argo CD에서 확인하세요", flush=True)

if __name__ == "__main__":
    try:
        config = json.loads(Path("/config/settings.json").read_text())
        Bootstrap(config, Kube(), Http(), os.environ["GITLAB_TOKEN"], "/config").run()
    except Exception as error:
        # 원격 응답이나 Secret 값을 출력하지 않습니다.
        if isinstance(error, (RuntimeError, ApiError)):
            print("연동 실패: " + str(error), flush=True)
        else:
            print("연동 실패: " + type(error).__name__ + " (인증정보·API·설정 확인)", flush=True)
        raise SystemExit(1)
