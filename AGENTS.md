# AGENTS.md — Analysis Tool For HyperOS

Python CLI that downloads HyperOS ROMs, extracts `payload.bin` / EROFS images and version-tracks APKs; JSON databases are split per device class (`phone/`, `fold/`, `pad/`, `flip/`, each with its own `app_code.json` / `app_version.json`). CI builds 8 platform zips to self-hosted OpenList (alpha/beta/stable) plus GitHub Releases for beta/stable; end-user usage is in `README.md`.

## Precedence

- Nearest `AGENTS.md` wins; an explicit user instruction wins over any file.
- When docs and code disagree, follow the code and report the inconsistency.

## Commands

| Purpose | Command |
| --- | --- |
| Install (only Python dep) | `pip install -r requirements.txt` (`androguard==4.1.4`) |
| Usage / all flags | `python3 main.py -h` (usual flow `-d` → `-p` → `-i` → `-f` → …) |
| Release script syntax | `bash -n ci/release-log.sh && bash -n ci/upload-openlist.sh` |
| Workflow YAML parse | `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/*.yml` |
| No server paths in source | `grep -rn '/www/' ci .github && echo FAIL \|\| echo OK` |

No test suite; the three checks above are all that exists locally. Runtime tools `aria2c`, `7z`, `payload-dumper-go` and `extract.erofs` are bundled in the distributed zips' `tools/`, not vendored in this repo.

## Boundaries

**Always**
- Use the `docs:` prefix for doc-only commits (`paths-ignore` skips the build; the release log filters doc/chore/ci/test/style/build).
- Keep `ci/release-log.sh` and `ci/upload-openlist.sh` standalone: `bash -n` clean and free of hard-coded server paths.

**Ask first**
- Renaming `build.yml` (alpha log range queries the Actions API by that filename); changing the tag regex, OpenList retention or artifact naming.
- Bumping `VERSION` — it must match the next release tag verbatim.

**Never**
- Hand-edit `release.md`, `changelog.txt` or `version.json` on the server — CI regenerates and uploads them; never add `v` prefixes or extra tag segments.
- Commit build output (`output/`, `*.zip`, `__pycache__/`, `venv/`).

General rules: `~/.config/opencode/AGENTS.md`.

## Release / CI

Push `main` → alpha (OpenList `alpha/`, no tag/Release); tag `x.y.z-beta.N` → beta + prerelease Release; tag `x.y.z` → stable. Tags are exactly those two shapes. Build ID = `github.run_number` = version code, monotonic and never reused — a withdrawn version does not free its ID. Artifact names `<repo>-<VERSION>-<BUILD_ID>-<platform>-<arch>.zip` are a public contract. `ci/release-log.sh <range>` emits `release.md` and `changelog.txt`; `Analysis.yml` is the separate on-demand ROM-analysis workflow.

## Pointers

- `-t` / `--devicetype` (`move_json` in `main.py`) switches which device-class JSON dictionary is active — know the class before editing data or running locally.
- Release rules/templates: `~/.config/opencode/docs/VERSIONING.md` (rules), `RELEASE-PIPELINE.md` (implementation), `COMMITTING.md`; shared across the three Analysis tools: `SISTER-REPOS.md`.
- CI pulls `payload-dumper-go` / `erofs-tools` from the GitHub API — upstream 500s are not this repo's fault, just rerun. The self-hosted runner's workspace persists, so check stale `output/` before trusting artifacts.
