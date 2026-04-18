import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "agent-worker"))

from incidentpilot.workflow import classify_issue, derive_root_cause


def main() -> int:
    cases_path = pathlib.Path(__file__).with_name("eval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    hits = 0
    for case in cases:
        issue = classify_issue(case["service"], case["symptom"], case["faults"])
        root_cause = derive_root_cause(case["service"], issue, case["faults"])
        ok = case["expected_keyword"].lower() in root_cause.lower()
        hits += int(ok)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']} issue={issue} root_cause={root_cause}")
    rate = hits / len(cases)
    print(f"hit_rate={rate:.2%} cases={len(cases)}")
    return 0 if rate >= 0.8 else 1


if __name__ == "__main__":
    raise SystemExit(main())

