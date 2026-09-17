"""PMC-001: deterministic synthetic development harness. No external code execution."""

import argparse
import hashlib
import json
from pathlib import Path


def answer(status, value=None, evidence=()):
    return {"status": status, "value": value, "evidence": sorted(evidence)}


def validate_record(record):
    if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
        raise ValueError("Missing record identifier")
    if record.get("type") == "retract":
        if set(record) != {"id", "type", "target"} or not isinstance(record["target"], str) or not record["target"]:
            raise ValueError("Invalid tombstone")
    elif record.get("type") == "assert":
        if set(record) != {"id", "type", "entity", "property", "value", "valid_from", "source"}:
            raise ValueError("Invalid assertion fields")
        if any(not isinstance(record[field], str) or not record[field] for field in ("entity", "property", "value", "source")):
            raise ValueError("Assertions require nonempty strings")
        if record["valid_from"] is not None and type(record["valid_from"]) is not int:
            raise ValueError("valid_from requires an integer or null")
    else:
        raise ValueError("Unknown record type")


def resolve(records, query):
    try:
        if not isinstance(records, list) or len(records) > 256 or not isinstance(query, dict) or set(query) != {"entity", "property"}:
            raise ValueError("Invalid input")
        if any(not isinstance(value, str) or not value for value in query.values()):
            raise ValueError("Invalid query")
        unique = {}
        for record in records:
            validate_record(record)
            if record["id"] in unique and unique[record["id"]] != record:
                raise ValueError("Identifier collision")
            unique[record["id"]] = record
        removed = {record["target"] for record in unique.values() if record["type"] == "retract"}
        if any(target in unique and unique[target]["type"] != "assert" for target in removed):
            raise ValueError("Retractions of retractions are outside the contract")
        claims = [record for record in unique.values() if record["type"] == "assert"
                  and record["id"] not in removed and all(record[field] == value for field, value in query.items())]
        if not claims:
            return answer("unknown")
        values = {record["value"] for record in claims}
        if len(values) == 1:
            return answer("known", claims[0]["value"], [record["id"] for record in claims])
        if any(record["valid_from"] is None for record in claims):
            return answer("unknown", evidence=[record["id"] for record in claims])
        latest = max(record["valid_from"] for record in claims)
        newest = [record for record in claims if record["valid_from"] == latest]
        if len({record["value"] for record in newest}) > 1:
            return answer("conflict", evidence=[record["id"] for record in newest])
        return answer("known", newest[0]["value"], [record["id"] for record in newest])
    except ValueError:
        return answer("invalid")


def latest_import(records, query):
    matching = [record for record in records if record.get("type") == "assert"
                and all(record.get(field) == value for field, value in query.items())]
    return answer("known", matching[-1]["value"], [matching[-1]["id"]]) if matching else answer("unknown")


def score(cases, predictions):
    case_ids = {case["id"] for case in cases}
    if len(case_ids) != len(cases) or not isinstance(predictions, dict) or set(predictions) - case_ids:
        raise ValueError("Duplicate case IDs or unknown prediction IDs")
    results = []
    for case in cases:
        predicted = predictions.get(case["id"])
        expected = case["expected"]
        valid = isinstance(predicted, dict) and set(predicted) == {"status", "value", "evidence"}
        if valid:
            valid = (isinstance(predicted["status"], str) and predicted["status"] in {"known", "unknown", "conflict", "invalid"}
                     and (predicted["value"] is None or isinstance(predicted["value"], str))
                     and isinstance(predicted["evidence"], list)
                     and all(isinstance(identifier, str) for identifier in predicted["evidence"]))
        exact = valid and predicted["status"] == expected["status"] and predicted["value"] == expected["value"] and sorted(predicted["evidence"]) == sorted(expected["evidence"])
        known = valid and predicted["status"] == "known"
        unsafe = known and (expected["status"] != "known" or predicted["value"] != expected["value"])
        results.append({"case_id": case["id"], "exact": bool(exact), "known_prediction": bool(known), "unsafe_known_prediction": bool(unsafe)})
    return {"cases": len(cases), "exact": sum(item["exact"] for item in results),
            "known_predictions": sum(item["known_prediction"] for item in results),
            "unsafe_known_predictions": sum(item["unsafe_known_prediction"] for item in results), "results": results}


def read_json(path):
    with path.open("rb") as stream:
        content = stream.read(131073)
    if len(content) > 131072:
        raise ValueError("Input exceeds 128 KiB")
    return json.loads(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--predictions", type=Path, help="JSON object mapping case ID to answer; data only")
    args = parser.parse_args()
    dataset = read_json(args.dataset)
    if dataset.get("schema") != "przystan-pmc-001/1":
        parser.error("Unsupported dataset schema")
    cases = dataset["cases"]
    methods = {"latest_import": latest_import, "reference_contract": resolve}
    reports = {name: score(cases, {case["id"]: method(case["records"], case["query"]) for case in cases}) for name, method in methods.items()}
    if args.predictions:
        reports["submitted_data"] = score(cases, read_json(args.predictions))
    print(json.dumps({"dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                      "interpretation": "public_synthetic_development_cases_not_model_or_migration_evaluation", "reports": reports}, indent=2))


if __name__ == "__main__":
    main()
