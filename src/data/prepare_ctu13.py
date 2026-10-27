"""CTU-13 binetflow -> model sequences, separate label audit, quality report.

Standard library only. SQLite stages rows on disk; memory holds one group.
Run from repo root: python -m src.data.prepare_ctu13 --help
"""

import argparse
import csv
import hashlib
import ipaddress
import itertools
import json
import re
import sqlite3
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REQUIRED = ("StartTime", "Proto", "SrcAddr", "DstAddr", "Dport", "SrcBytes", "Label", "Dir")
CATEGORY = re.compile(r"^(?:(?:From|To)-)?(Botnet|Normal|Background)(?:-|$)")
CC_TOKEN = re.compile(r"(?:^|-)CC\d+(?:-|$)")
SOURCE_URL = (
    "https://mcfp.felk.cvut.cz/publicDatasets/CTU-Malware-Capture-Botnet-42/"
    "detailed-bidirectional-flow-labels/capture20110810.binetflow"
)


def category(label):
    """Keep unknown labels unknown; never turn Botnet into beaconing."""
    match = CATEGORY.match(label.removeprefix("flow="))
    return match.group(1).lower() if match else "unknown"


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def parse_event(row):
    """Parse a selected TCP/UDP record; source/destination stay as recorded."""
    if None in row or any(row.get(name) is None for name in REQUIRED):
        raise ValueError("wrong_column_count")
    if any(not row[name].strip() for name in REQUIRED):
        raise ValueError("empty_required_value")
    stamp = datetime.strptime(row["StartTime"].strip(), "%Y/%m/%d %H:%M:%S.%f")
    src = str(ipaddress.ip_address(row["SrcAddr"].strip()))
    dst = str(ipaddress.ip_address(row["DstAddr"].strip()))
    # This export uses decimal ports. Unknown encodings are reported, not guessed.
    port = int(row["Dport"].strip())
    if not 0 <= port <= 65535:
        raise ValueError("port_out_of_range")
    byte_count = int(row["SrcBytes"].strip())
    if byte_count < 0:
        raise ValueError("negative_src_bytes")
    return (src, dst, port, row["Proto"].strip().lower(),
            stamp.isoformat(timespec="microseconds"), byte_count,
            row["Label"].strip(), row["Dir"].strip())


def convert(input_path, output_dir, dataset_id="ctu13-scenario01-tcp-bootstrap-v1",
            protocols=("tcp",), min_events=5, source_url=None):
    input_path, output_dir = Path(input_path), Path(output_dir)
    protocols = tuple(sorted(set(protocols)))
    if not dataset_id or "|" in dataset_id:
        raise ValueError("dataset_id must be nonempty and contain no '|'")
    if not protocols or set(protocols) - {"tcp", "udp"}:
        raise ValueError("protocols must be tcp and/or udp")
    if isinstance(min_events, bool) or not isinstance(min_events, int) or min_events < 2:
        raise ValueError("min_events must be an integer >= 2")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    source = {
        "dataset_id": dataset_id, "input_file": input_path.name,
        "sha256": fingerprint(input_path), "size_bytes": input_path.stat().st_size,
        "source_url": source_url,
        "timestamp_basis": "source_clock_timezone_unverified",
        "grouping_key": ["SrcAddr", "DstAddr", "Dport", "Proto"],
        "endpoint_policy": "preserve_recorded_endpoints_no_Dir_reorientation",
        "byte_field": "SrcBytes", "selected_protocols": list(protocols),
        "min_events": min_events,
        "purpose": "bootstrap_model_development_not_final_test_set",
    }
    quality = Counter({
        "total_rows": 0, "protocol_filtered_rows": 0, "invalid_selected_rows": 0,
        "accepted_rows": 0, "groups_before_min_events": 0,
        "short_groups": 0, "short_group_rows": 0,
        "exported_groups": 0, "exported_rows": 0, "zero_delta_count": 0,
        "all_zero_interval_groups": 0,
    })
    protocol_counts, rejected_reasons = Counter(), Counter()
    missing_ports, raw_labels = Counter(), Counter()
    exported_categories = Counter()
    examples = []
    # Temporary SQLite avoids keeping millions of Python objects in RAM.
    with tempfile.TemporaryDirectory(prefix="ctu13-stage-") as staging:
        with sqlite3.connect(str(Path(staging) / "events.sqlite")) as db:
            db.execute("PRAGMA cache_size=-32768")
            db.execute("PRAGMA temp_store=FILE")
            db.execute("CREATE TABLE events (src TEXT, dst TEXT, port INTEGER, proto TEXT, "
                       "stamp TEXT, nbytes INTEGER, label TEXT, direction TEXT, line INTEGER)")
            with input_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, skipinitialspace=True)
                fields = reader.fieldnames or []
                if len(fields) != len(set(fields)) or set(REQUIRED) - set(fields):
                    raise ValueError("Missing or duplicate header columns; expected: " + ", ".join(REQUIRED))
                for row in reader:
                    quality["total_rows"] += 1
                    protocol = (row.get("Proto") or "").strip().lower()
                    protocol_counts[protocol] += 1
                    raw_labels[(row.get("Label") or "").strip()] += 1
                    if not (row.get("Dport") or "").strip():
                        missing_ports[protocol] += 1
                    if protocol not in protocols:
                        quality["protocol_filtered_rows"] += 1
                    else:
                        try:
                            event = parse_event(row)
                        except (ValueError, TypeError, OverflowError) as error:
                            quality["invalid_selected_rows"] += 1
                            reason = str(error)
                            # Count by stable type, retain precise text in sample errors.
                            stable_reason = (reason if reason in {
                                "wrong_column_count", "empty_required_value",
                                "port_out_of_range", "negative_src_bytes"
                            } else "invalid_timestamp_ip_port_or_bytes")
                            rejected_reasons[stable_reason] += 1
                            if len(examples) < 10:
                                examples.append({"csv_line": reader.line_num, "error": reason})
                        else:
                            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                                       (*event, reader.line_num))
                            quality["accepted_rows"] += 1
                    if quality["total_rows"] % 250000 == 0:
                        db.commit()
                        print(f"Read {quality['total_rows']:,} rows...", flush=True)
            db.commit()
            if quality["accepted_rows"] == 0:
                raise ValueError("No valid selected records; check protocol/format before exporting")
            db.execute("CREATE INDEX event_order ON events(src,dst,port,proto,stamp,line)")
            # Stage output files together; summary.json is published last.
            with tempfile.TemporaryDirectory(dir=output_dir, prefix=".build-") as build:
                build = Path(build)
                with (build / "flows.json").open("w", encoding="utf-8") as flows_out, \
                     (build / "labels.json").open("w", encoding="utf-8") as labels_out:
                    flows_out.write('{"schema_version":"1.1","run_id":' + dump(run_id)
                                    + ',"source":' + dump(source) + ',"flows":[')
                    labels_out.write('{"schema_version":"1.0","run_id":' + dump(run_id)
                                     + ',"dataset_id":' + dump(dataset_id) + ',"labels":[')
                    first = True
                    cursor = db.execute("SELECT * FROM events ORDER BY src,dst,port,proto,stamp,line")
                    for key, records in itertools.groupby(cursor, key=lambda record: record[:4]):
                        quality["groups_before_min_events"] += 1
                        events = list(records)
                        if len(events) < min_events:
                            quality["short_groups"] += 1
                            quality["short_group_rows"] += len(events)
                            continue
                        times = [datetime.fromisoformat(event[4]) for event in events]
                        deltas = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
                        relative = [(stamp - times[0]).total_seconds() for stamp in times]
                        flow_id = "|".join((dataset_id, *(str(value) for value in key)))
                        label_counts = Counter(event[6] for event in events)
                        category_counts = Counter()
                        for label, count in label_counts.items():
                            category_counts[category(label)] += count
                        status = next(iter(category_counts)) if len(category_counts) == 1 else "mixed"
                        flow = {
                            "flow_id": flow_id, "src_ip": key[0], "dst_ip": key[1],
                            "dst_port": key[2], "protocol": key[3], "event_count": len(events),
                            "timestamps": [event[4] for event in events],
                            "timestamp_basis": "source_clock_timezone_unverified",
                            "relative_times_seconds": relative, "time_deltas": deltas,
                            "bytes_sent": [event[5] for event in events],
                            "bytes_semantics": "argus_src_bytes",
                        }
                        audit = {
                            "flow_id": flow_id, "event_count": len(events),
                            "category": status, "category_counts": dict(category_counts),
                            "raw_label_counts": dict(label_counts),
                            "cc_annotated_rows": sum(count for label, count in label_counts.items()
                                                     if CC_TOKEN.search(label)),
                            "direction_counts": dict(Counter(event[7] for event in events)),
                            "beaconing_ground_truth": "not_established",
                        }
                        if not first:
                            flows_out.write(",")
                            labels_out.write(",")
                        flows_out.write("\n" + dump(flow))
                        labels_out.write("\n" + dump(audit))
                        first = False
                        quality["exported_groups"] += 1
                        quality["exported_rows"] += len(events)
                        quality["zero_delta_count"] += sum(delta == 0 for delta in deltas)
                        quality["all_zero_interval_groups"] += int(all(delta == 0 for delta in deltas))
                        exported_categories[status] += 1
                    flows_out.write('],"quality":' + dump(dict(quality)) + '}\n')
                    labels_out.write("]}\n")
                assert quality["total_rows"] == (quality["protocol_filtered_rows"]
                        + quality["invalid_selected_rows"] + quality["accepted_rows"])
                assert quality["accepted_rows"] == quality["short_group_rows"] + quality["exported_rows"]
                summary = {
                    "run_id": run_id, "schema_version": "1.1", "source": source,
                    "quality": dict(quality), "protocol_counts_all_rows": dict(protocol_counts),
                    "missing_dport_by_protocol_all_rows": dict(missing_ports),
                    "raw_label_counts_all_rows": dict(raw_labels),
                    "rejected_selected_row_reasons": dict(rejected_reasons),
                    "rejected_selected_row_examples": examples,
                    "exported_group_categories": dict(exported_categories),
                    "notes": [
                        "No labels are model features; labels.json is for independent audit.",
                        "No duplicate records are dropped; equal timestamps preserve CSV order.",
                        "No endpoint reversal is inferred from Dir.",
                        "Short groups are excluded from this bootstrap export, not called benign.",
                        "Within-scenario clock differences are used without claiming UTC.",
                        "This export has no train/dev/test split and cannot support final test claims.",
                    ],
                }
                (build / "summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                for name in ("flows.json", "labels.json", "summary.json"):
                    (build / name).replace(output_dir / name)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", default="ctu13-scenario01-tcp-bootstrap-v1")
    parser.add_argument("--protocols", nargs="+", choices=("tcp", "udp"), default=["tcp"])
    parser.add_argument("--min-events", type=int, default=5)
    parser.add_argument("--source-url", default=None,
                        help="Provenance URL; use the URL actually downloaded")
    args = parser.parse_args(argv)
    try:
        result = convert(args.input, args.output_dir, args.dataset_id,
                         args.protocols, args.min_events, args.source_url)
    except (OSError, ValueError, sqlite3.Error, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result["quality"], indent=2))
    print("Missing Dport by protocol:", result["missing_dport_by_protocol_all_rows"])
    print("Exported group categories:", result["exported_group_categories"])
    print("Output:", args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
