"""검증된 Git revision을 배포할 Kubernetes ConfigMap으로 만듭니다."""
import re

def render_configmap(revision):
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision or ""):
        raise ValueError("Git revision 형식이 아닙니다")
    return {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "cicd-demo"},
            "data": {"revision": revision}}
