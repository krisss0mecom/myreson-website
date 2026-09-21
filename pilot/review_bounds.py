"""Independent operator check of user-relayed PMC bounds; not contributor code."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
READER = ROOT / "evaluate.py"
EXPECTED_READER = "5e56f090d46e61ca45f482f047cffd2176e164de88dc921d9967e632be4b5602"
if hashlib.sha256(READER.read_bytes()).hexdigest() != EXPECTED_READER:
    raise RuntimeError("Reference reader changed; review before running")
sys.path.insert(0, str(READER.parent))
from evaluate import read_json, resolve


QUERY = {"entity": "mira", "property": "city"}
SOURCE = "0" * 257
CHANGED_SOURCE = "0" * 256 + "1"


def assertion(position, source=SOURCE):
    return {
        "id": f"a{position:03d}", "type": "assert", "entity": "mira",
        "property": "city", "value": "Porto", "valid_from": 1, "source": source,
    }


def history(count, changed_position=None):
    records = []
    for position in range(count):
        source = CHANGED_SOURCE if position == changed_position else SOURCE
        record = assertion(position, source)
        records.extend([record, {"id": f"r{position:03d}", "type": "retract", "target": record["id"]}])
    return records


def case(identifier, records, expected_status):
    return {
        "id": identifier, "records": records, "query": QUERY,
        "expected": {"status": expected_status, "value": None, "evidence": []},
    }


def encode(cases):
    dataset = {"schema": "reson-pmc-001/1", "cases": cases}
    return (json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def run():
    basic = [
        case("single_s", history(1), "unknown"),
        case("single_t", history(1, 0), "unknown"),
        case("single_s_then_s", history(1) + [assertion(0)], "unknown"),
        case("single_t_then_s", history(1, 0) + [assertion(0)], "invalid"),
    ]
    cases = list(basic)
    for position in range(127):
        continuation = [assertion(position)]
        cases.extend([
            case(f"n127_{position:03d}_same", history(127) + continuation, "unknown"),
            case(f"n127_{position:03d}_changed", history(127, position) + continuation, "invalid"),
        ])
    cases.extend([
        case("n128_s_prefix", history(128), "unknown"),
        case("n128_t_prefix", history(128, 0), "unknown"),
        case("n128_s_then_s", history(128) + [assertion(0)], "invalid"),
        case("n128_t_then_s", history(128, 0) + [assertion(0)], "invalid"),
    ])
    results = []
    with tempfile.TemporaryDirectory(prefix="reson-bounds-") as temporary:
        path = Path(temporary) / "dataset.json"
        for item in cases:
            content = encode([item])
            path.write_bytes(content)
            loaded = read_json(path)
            if loaded["schema"] != "reson-pmc-001/1" or loaded["cases"] != [item]:
                raise AssertionError("Dataset round trip failed")
            loaded_case = loaded["cases"][0]
            actual = resolve(loaded_case["records"], loaded_case["query"])
            if actual != loaded_case["expected"]:
                raise AssertionError((item["id"], actual, item["expected"]))
            results.append({
                "case": item["id"], "records": len(item["records"]),
                "dataset_bytes": len(content), "dataset_sha256": hashlib.sha256(content).hexdigest(),
                "actual": actual, "expected": item["expected"], "passed": True,
            })
        content = encode(basic)
        path.write_bytes(content)
        if read_json(path)["cases"] != basic:
            raise AssertionError("Four-case dataset rejected or changed")
        four_case_bytes = len(content)
        path.write_bytes(b" " * 131073)
        try:
            read_json(path)
        except ValueError as error:
            if str(error) != "Input exceeds 128 KiB":
                raise
        else:
            raise AssertionError("Oversized input accepted")
    return {
        "schema": "reson-local-bounds-check/1",
        "reader_sha256": EXPECTED_READER,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "method": "Operator-authored independent checks; exact full answers; each case read through the 128 KiB JSON guard before resolve.",
        "serialization": "UTF-8, ensure_ascii=True, sort_keys=True, compact separators, one trailing newline; dataset and case metadata included.",
        "answer_comparisons": len(results),
        "answer_comparisons_passed": sum(item["passed"] for item in results),
        "additional_input_checks": {"four_case_dataset_accepted": True, "131073_byte_input_rejected": True},
        "four_case_dataset_bytes": four_case_bytes,
        "n127_one_case_bytes": next(item["dataset_bytes"] for item in results if item["case"] == "n127_000_same"),
        "largest_one_case_bytes": max(item["dataset_bytes"] for item in results),
        "checks": results,
        "not_executed_or_proven": [
            "The contributor's claimed 263-check script and exact 2950/52732-byte serializations were not provided.",
            "Enumeration of all 2**257 source strings or all 2**32639 histories.",
            "SHA-256 collision search, any compact exporter/importer, model migration or model benchmark.",
            "Question 4's proposed generator, temporal interval policy or claimed accuracy.",
            "Minimality or sufficiency of an export, or the largest admissible source alphabet.",
        ],
    }


if __name__ == "__main__":
    report = run()
    checks = report.pop("checks")
    report["detailed_checks_sha256"] = hashlib.sha256(json.dumps(checks, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report["checks"] = [
        {"case": "bounds_source257", "answers": [item["actual"] for item in checks[:4]], "expected_statuses": ["unknown", "unknown", "unknown", "invalid"], "source_length": 257, "passed": True},
        {"case": "bounds_n127", "changed_positions": 127, "pairs": 127, "records_per_continuation": 255, "same_statuses": sorted({item["actual"]["status"] for item in checks[4:258:2]}), "changed_statuses": sorted({item["actual"]["status"] for item in checks[5:258:2]}), "passed": True},
        {"case": "bounds_n128_cap", "answers": [item["actual"] for item in checks[-4:]], "record_counts": [item["records"] for item in checks[-4:]], "passed": True},
        {"case": "bounds_input_sizes", "four_case_bytes": report["four_case_dataset_bytes"], "n127_one_case_bytes": report["n127_one_case_bytes"], "largest_one_case_bytes": report["largest_one_case_bytes"], "oversized_input_rejected": True, "passed": True},
    ]
    report["not_proven"] = report.pop("not_executed_or_proven")
    print(json.dumps(report, indent=2))
