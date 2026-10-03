from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from commerce_support_demo.main import create_app
from commerce_support_demo.settings import Settings


def main() -> None:
    settings = Settings.from_environment()
    if settings.router_mode != "offline":
        raise SystemExit(
            "The checked-in evaluator is offline-only; live API evaluation "
            "needs explicit separate approval."
        )
    project_root = Path(__file__).resolve().parents[2]
    cases_path = project_root / "evals" / "cases_test.jsonl"
    cases = [
        json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line
    ]
    results = []
    with TestClient(create_app(settings)) as client:
        for case in cases:
            response = client.post(
                f"/v1/conversations/{case['conversation_id']}/messages",
                json=case["request"],
            )
            body = response.json()
            passed = (
                response.status_code == 200
                and body.get("route", {}).get("intent") == case["expected_intent"]
            )
            results.append(
                {
                    "case_id": case["case_id"],
                    "passed": passed,
                    "actual": body.get("route", {}).get("intent"),
                }
            )
    passed = sum(result["passed"] for result in results)
    report = {
        "schema_version": "1.0",
        "is_synthetic": True,
        "mode": "offline",
        "generated_at": datetime.now(UTC).isoformat(),
        "cases": len(results),
        "passed": passed,
        "intent_accuracy": round(passed / len(results), 4) if results else 0,
        "results": results,
    }
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "offline-evaluation.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("cases", "passed", "intent_accuracy")}, ensure_ascii=False
        )
    )
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
