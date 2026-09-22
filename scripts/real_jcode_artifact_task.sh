#!/usr/bin/env bash
# Genuine jcode -> separate scratch generation -> EXACT operator-selected file -> actual pytest.
set -euo pipefail
ROOT="${RUNNER_TEMP:-/tmp}/chimera-real-artifact"
mkdir -p "$ROOT"
git clone --depth 1 --quiet https://github.com/msitarzewski/agency-agents.git "$ROOT/agency-agents"
mkdir -p "$ROOT/project"
cd "$ROOT/project"
git init -q
cat > test_artifact.py <<'PY'
from pathlib import Path

def test_real_generated_file():
    assert Path("a.txt").read_text(encoding="utf-8").strip() == "ok"
PY
cat > .gitignore <<'EOF'
__pycache__/
.pytest_cache/
EOF
git add test_artifact.py .gitignore
git -c user.name="Real CI Task" -c user.email="real-ci@example.invalid" \
  commit -qm "Independently defined acceptance test"
cd "$GITHUB_WORKSPACE"
set +e
python -m chimera.jcode_artifact_cli \
  --agency-checkout "$ROOT/agency-agents" \
  --workspace "$ROOT/project" \
  --target a.txt --test-suite pytest \
  --task 'Generate the exact two lowercase letters ok as the complete UTF-8 content of one plain text file. No filename or shell commands are required. Do not add explanation.' \
  --jcode jcode --timeout 300 --execute > "$ROOT/report.json"
result=$?
set -e
python - "$ROOT/report.json" "$ROOT/project" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
if not path.exists() or not path.stat().st_size:
    raise SystemExit("Missing real jcode artifact result")
report = json.loads(path.read_text())
print("REAL_JCODE_ARTIFACT_STATUS=" + str(report.get("status")))
print("REAL_JCODE_CONTENT_SHA256=" + str(report.get("content_sha256")))
print("REAL_JCODE_TEST_STATUS=" + str(report.get("test_status")))
if report.get("status") == "candidate_for_human_review":
    assert report["generator"] == "real_upstream_jcode"
    assert report["tests_passed"] is True
    assert report["human_approval_required"] is True
    assert report["committed"] is False and report["deployed"] is False
    assert pathlib.Path(sys.argv[2], "a.txt").read_text().strip() == "ok"
    print("REAL_JCODE_CONTENT_TO_FILE_TO_PYTEST=PASS")
else:
    raise SystemExit("Genuine model generation or actual acceptance tests failed")
PY
if [ "$result" -ne 0 ]; then exit "$result"; fi
