"""업로드한 이미지의 Kustomize 배포 설정을 갱신합니다."""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import yaml


def update_image(text, image, revision):
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision or ""):
        raise ValueError("Git 커밋번호 형식을 확인하세요")
    obj = yaml.safe_load(text)
    if not isinstance(obj, dict) or obj.get("kind") != "Kustomization":
        raise ValueError("배포 경로에 Kustomization이 필요합니다")
    images = obj.get("images", [])
    entries = [entry for entry in images if isinstance(entry, dict) and entry.get("name") == "cicd-app"]
    if len(entries) != 1:
        raise ValueError("images에 name: cicd-app 항목 하나가 필요합니다")
    entry = entries[0]
    if entry.get("newName") == image and entry.get("newTag") == revision and "digest" not in entry:
        return None
    entry.update(newName=image, newTag=revision)
    entry.pop("digest", None)
    return yaml.safe_dump(obj, sort_keys=False)


def main():
    api = os.environ["CICD_API"].rstrip("/")
    project = str(int(os.environ["CICD_PROJECT"]))
    branch, path = os.environ["CICD_BRANCH"], os.environ["CICD_PATH"]
    headers = {"PRIVATE-TOKEN": os.environ["GITOPS_TOKEN"], "Content-Type": "application/json"}
    encoded_path = urllib.parse.quote(path, safe="")
    query = urllib.parse.urlencode({"ref": branch})
    request = urllib.request.Request(f"{api}/projects/{project}/repository/files/{encoded_path}?{query}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        current = json.load(response)
    content = update_image(base64.b64decode(current["content"]).decode(), os.environ["CICD_IMAGE"], os.environ["CICD_REVISION"])
    if content is None:
        print("이미 같은 이미지입니다")
        return
    data = {"branch": branch, "commit_message": "Deploy image " + os.environ["CICD_REVISION"],
            "actions": [{"action": "update", "file_path": path, "content": content,
                         "last_commit_id": current["last_commit_id"]}]}
    request = urllib.request.Request(f"{api}/projects/{project}/repository/commits", method="POST",
                                     headers=headers, data=json.dumps(data).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
    print("새 이미지 주소와 태그를 배포 저장소에 반영했습니다")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("GitOps 반영 실패: HTTP", error.code)
        raise SystemExit(1)
