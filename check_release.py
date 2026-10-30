"""Fail closed until the requested full scope is actually verified."""
import json
from pathlib import Path


def release_errors(gate, coverage):
    errors = []
    if not gate.get("latest_validation", {}).get("full_parity_verified"):
        errors.append("Full behavioral and numerical parity has not been verified.")
    for item in coverage.get("items", []):
        if not all(item.get(key) is True for key in (
            "native_behavior_complete", "implemented_complete", "reference_comparison_passed"
        )):
            errors.append("Coverage is incomplete: " + item["id"])
    if not coverage.get("items"):
        errors.append("The full feature coverage manifest is absent or empty.")
    if coverage.get("additional_required_scopes") and not coverage.get("additional_scopes_verified"):
        errors.append("Additional engine, language, graph, format and integration scopes remain open.")
    return errors


def main():
    workspace = Path(__file__).resolve().parents[2]
    gate = json.loads((workspace / "work/deliverable-gate.json").read_text(encoding="utf-8-sig"))
    coverage = json.loads((workspace / "outputs/statcraft-full-scope-coverage.json").read_text(encoding="utf-8-sig"))
    errors = release_errors(gate, coverage)
    if errors:
        print("StatCraft executable release is blocked:")
        for error in errors[:6]:
            print("- " + error)
        print(f"{len(errors)} incomplete coverage/verification checks. No executable was built.")
        return 1
    print("All recorded full-scope release checks passed; executable build is eligible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
