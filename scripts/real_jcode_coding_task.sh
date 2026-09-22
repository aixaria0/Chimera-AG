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
    assert Path("a.txt").read_text(encoding="utf-8").strip() == "ok"
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
set +e
timeout 900s python -m chimera.coding_cli \
  --agency-checkout "$WORK_ROOT/agency-agents" \
  --workspace "$WORK_ROOT/project" \
  --task 'Create a.txt. Its contents must be exactly the two lowercase letters ok. Do not modify the tests, and do not perform other actions.' \
  --jcode jcode --test-suite pytest \
  --declarative-write-path a.txt --execute \
  > "$WORK_ROOT/result.json"
coding_exit=$?
set -e
# This CI fixture contains only public prompts; emit narrow diagnostic
# fields without printing the full role/model transcript.
python - "$WORK_ROOT/result.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.exists() or not path.stat().st_size:
    print("REAL_CODING_REPORT_MISSING")
else:
    try:
        report = json.loads(path.read_text())
        print("REAL_CODING_STATUS=" + str(report.get("status")))
        for phase in report.get("phases", []):
            print("PHASE=" + phase["name"] + " STATUS=" + phase["status"]
                  + " RC=" + str(phase["returncode"]) + " OUTPUT_LENGTH="
                  + str(len(phase["output_preview"])) + " DIGEST=" + phase["output_digest"] + " OUTPUT=" + repr(phase["output_preview"][:850]))
    except (ValueError, KeyError, TypeError):
        print("REAL_CODING_REPORT_INVALID_JSON")
PY
if [ "$coding_exit" -ne 0 ]; then
  exit "$coding_exit"
fi
python - "$WORK_ROOT/result.json" "$WORK_ROOT/project" <<'PY'
import json, pathlib, sys
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert report["status"] in ("candidate_for_human_review", "tests_passed_review_inconclusive"), report["status"]
assert len(report["constrained_model_edits"]) == 1, report["constrained_model_edits"]
assert report["constrained_model_edits"][0]["path"] == "a.txt"
assert [p["status"] for p in report["phases"]] == ["completed"] * 4
assert pathlib.Path(sys.argv[2], "a.txt").read_text().strip() == "ok"
assert report["human_approval_required"] is True
assert report["committed"] is False and report["deployed"] is False
print("REAL_JCODE_AGENCY_CODING_PIPELINE=PASS review_inconclusive=" + str(report["review_inconclusive"]))
PY
