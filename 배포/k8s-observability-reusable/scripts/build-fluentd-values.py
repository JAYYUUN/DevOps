#!/usr/bin/env python3
"""분리된 Fluentd .conf 파일을 Helm fileConfigs values로 변환 (표준 라이브러리만 사용)."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
config_dir = root / "fluentd" / "config"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / ".generated" / "fluentd-pipeline.yaml"
out.parent.mkdir(parents=True, exist_ok=True)
files = sorted(config_dir.glob("*.conf"))
if not files:
    raise SystemExit("오류: fluentd/config/*.conf 파일이 없습니다")
lines = ["fileConfigs:"]
for f in files:
    lines.append(f"  {f.name}: |-")
    lines.extend("    " + line for line in f.read_text(encoding="utf-8").rstrip("\n").split("\n"))
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out)
