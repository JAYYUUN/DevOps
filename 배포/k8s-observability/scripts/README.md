# Scripts — 실행 보조

| 파일 | 역할 | 실행 |
|---|---|---|
| `load-env.sh` | `.env`를 읽어 Helmfile 환경변수 설정 | `source scripts/load-env.sh` |
| `check.sh` | Pod·PVC·Service·Helm 릴리스 상태 출력 | `./scripts/check.sh` |
| `export-live-values.sh` | 설치된 릴리스의 사용자 설정값 내보내기 | `./scripts/export-live-values.sh` |

모든 명령은 **프로젝트 루트**에서 실행합니다. `load-env.sh`는 현재 셸에 환경변수를 적용해야 하므로 `source`를 사용합니다.

배포 명령은 `helmfile repos` → `helmfile sync`입니다.
