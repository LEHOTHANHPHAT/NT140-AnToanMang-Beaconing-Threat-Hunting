import argparse
import csv
import math
from pathlib import Path

CC_TARGETS = [
    ("147.32.84.165", "222.88.205.195", "443", "tcp"),
    ("147.32.84.165", "31.192.109.167", "80", "tcp"),
    ("147.32.84.165", "213.246.53.125", "5296", "tcp"),
    ("147.32.84.165", "61.17.216.4", "6667", "tcp"),
    ("147.32.84.165", "61.167.116.133", "6667", "tcp"),
    ("147.32.84.165", "173.192.170.88", "80", "tcp"),
    ("147.32.84.165", "60.190.223.75", "888", "tcp"),
]


def endpoint_key(flow_id):
    # flow_id = dataset|src_ip|dst_ip|dst_port|protocol
    parts = flow_id.rsplit("|", 4)
    if len(parts) != 5:
        raise ValueError(f"flow_id không đúng định dạng: {flow_id}")
    return tuple(parts[1:])


def display_group(row):
    src, dst, port, proto = endpoint_key(row["flow_id"])
    return f"{src} → {dst}:{port}/{proto}"


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(
            {column: row.get(column, "") for column in columns}
            for row in rows
        )


def markdown_table(rows, columns):
    def escape(value):
        return str(value).replace("|", r"\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(escape(row.get(c, "")) for c in columns) + " |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Path(args.input).open(
        newline="", encoding="utf-8-sig"
    ) as f:
        reader = csv.DictReader(f)
        required = {
            "flow_id", "event_count", "score", "status",
            "category", "cc_annotated_rows",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Thiếu các cột: {sorted(missing)}")
        rows = list(reader)

    seen_ids = set()
    for row in rows:
        if row["flow_id"] in seen_ids:
            raise ValueError(f"Trùng flow_id: {row['flow_id']}")
        seen_ids.add(row["flow_id"])

        row["event_count"] = int(row["event_count"])
        row["cc_annotated_rows"] = int(row["cc_annotated_rows"])
        endpoint_key(row["flow_id"])

        if row["status"] == "ok":
            row["_score"] = float(row["score"])
            if not math.isfinite(row["_score"]):
                raise ValueError(f"Điểm không hữu hạn: {row['flow_id']}")

    thresholds = {"A": None, "B": 10, "C": 20}
    ranked = {}
    summaries = []
    report_sections = []

    top_columns = [
        "rank", "group", "event_count", "score",
        "status", "category", "cc_annotated_rows",
    ]

    for name, minimum in thresholds.items():
        selected = [
            row for row in rows
            if row["status"] == "ok"
            and (minimum is None or row["event_count"] >= minimum)
        ]

        # Đồng điểm đầy đủ: sắp flow_id tăng dần.
        selected.sort(key=lambda row: (-row["_score"], row["flow_id"]))

        ranked[name] = {
            row["flow_id"]: position
            for position, row in enumerate(selected, start=1)
        }

        all_ranked = []
        for position, row in enumerate(selected, start=1):
            all_ranked.append({
                **row,
                "rank": position,
                "group": display_group(row),
                "score": format(row["_score"], ".17g"),
            })

        top = all_ranked[:20]
        csv_columns = ["flow_id"] + top_columns

        write_csv(
            out_dir / f"{name}_all_ranked.csv",
            all_ranked,
            csv_columns,
        )
        write_csv(
            out_dir / f"{name}_top20.csv",
            top,
            csv_columns,
        )

        summary = {
            "table": name,
            "min_events": "không thêm ngưỡng" if minimum is None else minimum,
            "eligible_groups": len(selected),
            "top_count": len(top),
            "normal_top20": sum(r["category"] == "normal" for r in top),
            "background_top20": sum(
                r["category"] == "background" for r in top
            ),
            "botnet_top20": sum(r["category"] == "botnet" for r in top),
            "cc_annotated_groups_eligible": sum(
                r["cc_annotated_rows"] > 0 for r in selected
            ),
        }
        summaries.append(summary)

        # Chỉ làm tròn để hiển thị Markdown.
        display_top = [
            {**row, "score": f"{float(row['score']):.6f}"}
            for row in top
        ]
        report_sections.append(
            f"## Bảng {name}\n\n"
            + markdown_table(display_top, top_columns)
        )

    tracking = []
    for target in CC_TARGETS:
        matches = [
            row for row in rows
            if endpoint_key(row["flow_id"]) == target
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Nhóm {target}: tìm thấy {len(matches)} dòng; cần đúng 1."
            )

        row = matches[0]
        entry = {
            "flow_id": row["flow_id"],
            "group": display_group(row),
            "event_count": row["event_count"],
            "score": row["score"],
            "status": row["status"],
            "cc_annotated_rows": row["cc_annotated_rows"],
        }

        for name, minimum in thresholds.items():
            if row["status"] != "ok":
                entry[f"rank_{name}"] = "không xét: status khác ok"
            elif minimum is not None and row["event_count"] < minimum:
                entry[f"rank_{name}"] = "bị loại: thiếu bản ghi"
            else:
                entry[f"rank_{name}"] = ranked[name][row["flow_id"]]

        tracking.append(entry)

    tracking_columns = [
        "group", "event_count", "score", "status",
        "cc_annotated_rows", "rank_A", "rank_B", "rank_C",
    ]
    write_csv(
        out_dir / "cc_tracking.csv",
        tracking,
        ["flow_id"] + tracking_columns,
    )

    summary_columns = list(summaries[0])
    write_csv(out_dir / "summary.csv", summaries, summary_columns)

    report = (
        "# Phân tích baseline theo số bản ghi tối thiểu\n\n"
        "Điểm được giữ nguyên từ CSV đầu vào. "
        "Xếp theo điểm giảm dần; nếu bằng điểm đầy đủ, "
        "sắp flow_id tăng dần. Hạng là vị trí tuần tự trong từng tập.\n\n"
        "CC là chú thích trong dữ liệu, chưa phải beacon đã xác minh.\n\n"
        "## Tổng hợp\n\n"
        + markdown_table(summaries, summary_columns)
        + "\n\n"
        + "\n\n".join(report_sections)
        + "\n\n## Theo dõi bảy nhóm CC\n\n"
        + markdown_table(tracking, tracking_columns)
        + "\n"
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print(f"Đã xuất kết quả vào: {out_dir.resolve()}")


if __name__ == "__main__":
    main()