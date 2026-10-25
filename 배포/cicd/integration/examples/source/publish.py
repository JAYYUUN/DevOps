"""CI 성공 뒤 배포 저장소의 ConfigMap revision을 GitLab API로 갱신합니다."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from app import render_configmap


def main():
    api = os.environ["CICD_API"].rstrip("/")
    project = str(int(os.environ["CICD_PROJECT"]))
    branch = os.environ["CICD_BRANCH"]
    path = os.environ["CICD_PATH"]
    content = json.dumps(render_configmap(os.environ["CICD_REVISION"]), indent=2) + "\n"
    headers = {"PRIVATE-TOKEN": os.environ["GITOPS_TOKEN"], "Content-Type": "application/json"}
    encoded_path = urllib.parse.quote(path, safe="")
    query = urllib.parse.urlencode({"ref": branch})
    request = urllib.request.Request(f"{api}/projects/{project}/repository/files/{encoded_path}?{query}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        current = json.load(response)
    if base64.b64decode(current["content"]).decode() == content:
        print("이미 같은 revision입니다")
        return
    data = {"branch": branch, "commit_message": "Publish verified revision " + os.environ["CICD_REVISION"],
            "actions": [{"action": "update", "file_path": path, "content": content,
                         "last_commit_id": current["last_commit_id"]}]}
    request = urllib.request.Request(f"{api}/projects/{project}/repository/commits", method="POST",
                                     headers=headers, data=json.dumps(data).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
    print("검증한 revision을 배포 저장소에 반영했습니다")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("GitOps 반영 실패: HTTP", error.code)
        raise SystemExit(1)
