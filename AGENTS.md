# AGENTS.md

Analysis Tool For HyperOS: a Python CLI that downloads HyperOS ROMs, extracts `payload.bin` / EROFS images, and pulls, renames and version-tracks APKs. The JSON databases are **split per device class** (`phone/` `fold/` `pad/` `flip/`, each with its own `app_code.json` / `app_version.json`). End-user usage and downloads are in `README.md` — this file is for maintaining the tool and its release pipeline.

Distribution: 8 platform zips built by CI, shipped to the self-hosted OpenList (three channels: 内测版 alpha / 公测版 beta / 正式版 stable) plus GitHub Releases for beta/stable only.

## Commands

```bash
pip install -r requirements.txt   # androguard — the only Python dep
python3 main.py -h                # all flags; the usual flow is -d → -p → -i → -f → …

# Local sanity checks before pushing CI changes (no test suite exists)
bash -n ci/release-log.sh && bash -n ci/upload-openlist.sh
python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/*.yml
grep -rn '/www/' ci .github && echo "FAIL: server paths in source" || echo "OK"
```

Runtime tools the scripts shell out to: `aria2c`, `7z`, plus `payload-dumper-go` / `extract.erofs` — bundled inside the distributed zips' `tools/`, **not** vendored in the repo.

## Release / CI

- **Versioning, channels, tag rules and the release-log template are specified in `~/.config/opencode/VERSIONING.md` — read it before touching any CI file** (build.yml encodes its rules, e.g. "Build ID = `github.run_number` = version_code, monotonic, never reused").
- Flow in short: push `main` → alpha build → OpenList `alpha/` (single version, no tag, no Release); `git tag x.y.z-beta.N` → beta + prerelease Release; `git tag x.y.z` → stable + Release. Tags must be exactly `x.y.z` or `x.y.z-beta.N` — the workflow rejects anything else.
- `ci/release-log.sh <range>` generates two files: `release.md` (Markdown, OpenList README / Release notes) and `changelog.txt` (plain text for `version.json`). It filters out `docs/chore/ci/test/style/build` commit types — **doc-only commits must use the `docs:` prefix** or they pollute the update log (and `*.md`/`docs/**` pushes skip the build entirely via paths-ignore).
- Artifact names are a public contract: `<repo>-<VERSION>-<BUILD_ID>-<platform>-<arch>.zip`, identical in `output/`, Release assets and OpenList; never rename history.
- `Analysis.yml` is the on-demand ROM-analysis workflow (workflow_dispatch: device type, ROM link, optional DB upload) — unrelated to releases.

## Boundaries

**Always**
- Read `~/.config/opencode/VERSIONING.md` first, then keep every release-flow change consistent with it (this file and the workflow comments cite its sections).
- Keep `ci/release-log.sh` / `ci/upload-openlist.sh` runnable standalone (`bash -n` clean) and free of hard-coded server paths.

**Ask first**
- Renaming `build.yml` (the alpha log range queries the Actions API by that exact filename).
- Changing the tag regex, the OpenList retention policy (`ci/upload-openlist.sh`), or the artifact naming.
- Bumping `VERSION` (it must match the next release tag verbatim).

**Never**
- Hand-edit `release.md` / `changelog.txt` / `version.json` on the server — CI regenerates and uploads them.
- Add `v` prefixes or extra segments to tags.
- Commit build output (`output/`, `*.zip`, `__pycache__/`, `venv/`).

## Known pitfalls

- **Upstream 500s**: CI pulls latest releases of `ssut/payload-dumper-go` and `sekaiacg/erofs-utils` via the GitHub API — when it flakes, the build goes red for no fault of this repo. **Just rerun.**
- **Withdrawn versions don't free their Build ID**: after rolling back `beta.2`, the next beta must be `beta.3`.
- **The self-hosted runner's workspace persists across runs** — stale `output/` from a previous run can confuse local verification; check before trusting artifacts.
- The JSON databases are the product's core data: `-t` (`move_json`) rewrites which device-class dictionary is active — know which class you're editing before running it locally.
