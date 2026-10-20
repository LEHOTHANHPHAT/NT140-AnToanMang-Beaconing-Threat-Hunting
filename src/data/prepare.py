"""Convert the documented sample CSV into grouped communication sequences."""

import csv
import ipaddress
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FIELDS = (
    "timestamp", "src_ip", "dst_ip", "dst_port", "protocol", "bytes_sent"
)


def parse_timestamp(value):
    """Return an aware UTC datetime; naive sample values are assumed to be UTC."""
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    assumed_utc = parsed.tzinfo is None
    if assumed_utc:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc), assumed_utc


def prepare_csv(input_path, dataset_id="sample"):
    """Validate every row before returning data. Invalid rows raise ValueError.

    This adapter is for the six-column sample format, not raw CTU-13 exports.
    Equal timestamps keep their original CSV order. Exact duplicates are kept
    and counted, because silently dropping events can change timing patterns.
    """
    input_path = Path(input_path)
    if not dataset_id or "|" in dataset_id:
        raise ValueError("dataset_id must be nonempty and must not contain '|'.")
    groups = defaultdict(list)
    seen = set()
    total = duplicates = assumed_utc_count = 0
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV header is missing or contains duplicate column names.")
        missing = set(REQUIRED_FIELDS) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        for row in reader:
            try:
                if None in row:
                    raise ValueError("too many columns")
                if any(row.get(name) is None or not row[name].strip() for name in REQUIRED_FIELDS):
                    raise ValueError("a required value is empty")
                stamp, assumed = parse_timestamp(row["timestamp"])
                src = str(ipaddress.ip_address(row["src_ip"].strip()))
                dst = str(ipaddress.ip_address(row["dst_ip"].strip()))
                port = int(row["dst_port"])
                byte_count = int(row["bytes_sent"])
                protocol = row["protocol"].strip().lower()
                if not 0 <= port <= 65535:
                    raise ValueError("dst_port must be between 0 and 65535")
                if byte_count < 0:
                    raise ValueError("bytes_sent must be nonnegative")
                if "|" in protocol:
                    raise ValueError("protocol must not contain '|'")
            except (ValueError, TypeError) as error:
                raise ValueError(f"{input_path.name}: CSV line {reader.line_num}: {error}") from error
            key = (src, dst, port, protocol)
            signature = (key, stamp, byte_count)
            duplicates += int(signature in seen)
            seen.add(signature)
            groups[key].append((stamp, byte_count))
            assumed_utc_count += int(assumed)
            total += 1
    if total == 0:
        raise ValueError("CSV contains no communication events.")
    flows = []
    for key, events in sorted(groups.items()):
        events.sort(key=lambda event: event[0])
        flows.append({
            "flow_id": "|".join((dataset_id, *(str(value) for value in key))),
            "src_ip": key[0],
            "dst_ip": key[1],
            "dst_port": key[2],
            "protocol": key[3],
            "event_count": len(events),
            "timestamps": [stamp.isoformat().replace("+00:00", "Z") for stamp, _ in events],
            "time_deltas": [
                (events[index][0] - events[index - 1][0]).total_seconds()
                for index in range(1, len(events))
            ],
            "bytes_sent": [byte_count for _, byte_count in events],
            "bytes_semantics": "originator_sent_bytes",
        })
    return {
        "schema_version": "1.0",
        "source": {"dataset_id": dataset_id, "input_file": input_path.name},
        "quality": {
            "event_count": total,
            "flow_count": len(flows),
            "naive_timestamps_assumed_utc": assumed_utc_count,
            "exact_duplicate_events_kept": duplicates,
        },
        "flows": flows,
    }


def save_json(payload, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
