#!/usr/bin/env bash
# Live, non-mocked coding task. Requires jcode configured to real Ollama.
set -euo pipefail
WORK_ROOT="${RUNNER_TEMP:-/tmp}/chimera-real-coding"
mkdir -p "$WORK_ROOT"
git clone --depth 1 --quiet https://github.com/msitarzewski/agency-agents.git "$WORK_ROOT/agency-agents"
mkdir -p "$WORK_ROOT/project"
cd "$WORK_ROOT/project"
git init -q
cat > test_answer.py <<'PY'
from pathlib import Path

def test_coding_agent_created_real_file():
    assert Path("ANSWER.txt").read_text(encoding="utf-8").strip() == "CHIMERA_REAL_CODING"
PY
cat > .gitignore <<'EOF'
__pycache__/
.pytest_cache/
.jcode/
EOF
git add test_answer.py .gitignore
git -c user.name="CI Fixture" -c user.email="ci-fixture@example.invalid" \
  commit -qm "Independent coding-task test"
cd "$GITHUB_WORKSPACE"
# No mocked agent calls. The real installed jcode binary must plan, edit,
# review and the fixed pytest suite must then accept the real edited file.
timeout 900s python -m chimera.coding_cli \
  --agency-checkout "$WORK_ROOT/agency-agents" \
  --workspace "$WORK_ROOT/project" \
  --task 'Create ANSWER.txt containing exactly CHIMERA_REAL_CODING and a trailing newline. Do not alter tests or git settings. This is a one-file task.' \
  --jcode jcode --test-suite pytest --execute \
  > "$WORK_ROOT/result.json"
python - "$WORK_ROOT/result.json" "$WORK_ROOT/project" <<'PY'
import json, pathlib, sys
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert report["status"] == "candidate_for_human_review", report["status"]
assert [p["status"] for p in report["phases"]] == ["completed"] * 4
assert pathlib.Path(sys.argv[2], "ANSWER.txt").read_text().strip() == "CHIMERA_REAL_CODING"
assert report["human_approval_required"] is True
assert report["committed"] is False and report["deployed"] is False
print("REAL_JCODE_AGENCY_CODING_PIPELINE=PASS")
PY
