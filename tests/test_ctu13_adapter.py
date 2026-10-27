"""Behavior checks for CTU-13 conversion; all fixtures are synthetic."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.data.prepare_ctu13 import category, convert

FIELDS = "StartTime,Dur,Proto,SrcAddr,Sport,Dir,DstAddr,Dport,State,sTos,dTos,TotPkts,TotBytes,SrcBytes,Label".split(",")


def event(second=0, nbytes=100, **changes):
    row = dict(zip(FIELDS, [
        f"2011/08/10 10:00:{second:02}.000000", "1.0", "tcp", "192.0.2.1", "12345",
        "->", "198.51.100.1", "80", "S_S", "0", "0", "2", "300", str(nbytes),
        "flow=From-Normal-V42-Stribrek",
    ]))
    row.update(changes)
    return row


class TestCTU13Adapter(unittest.TestCase):
    def run_conversion(self, rows, min_events=2):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.binetflow"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            summary = convert(source, root / "out", "fixture", min_events=min_events)
            flows = json.loads((root / "out/flows.json").read_text())
            labels = json.loads((root / "out/labels.json").read_text())
        return summary, flows, labels

    def test_sort_keeps_bytes_and_labels_with_events(self):
        rows = [event(30, 303, Label="flow=From-Botnet-V42-TCP-CC16-HTTP-Not-Encrypted"),
                event(0, 101), event(10, 202)]
        _, payload, labels = self.run_conversion(rows)
        flow = payload["flows"][0]
        self.assertEqual(flow["time_deltas"], [10, 20])
        self.assertEqual(flow["relative_times_seconds"], [0, 10, 30])
        self.assertEqual(flow["bytes_sent"], [101, 202, 303])
        self.assertEqual(labels["labels"][0]["category"], "mixed")
        self.assertEqual(labels["labels"][0]["cc_annotated_rows"], 1)

    def test_reversed_rows_distinct_times_give_same_flows(self):
        rows = [event(0, 10), event(10, 20), event(20, 30)]
        self.assertEqual(self.run_conversion(rows)[1]["flows"],
                         self.run_conversion(list(reversed(rows)))[1]["flows"])

    def test_port_separates_groups_but_source_port_does_not(self):
        rows = [event(0), event(10, Sport="9999"), event(20, Dport="443")]
        summary, payload, _ = self.run_conversion(rows)
        self.assertEqual(summary["quality"]["groups_before_min_events"], 2)
        self.assertEqual(summary["quality"]["short_groups"], 1)
        self.assertEqual(payload["flows"][0]["event_count"], 2)

    def test_missing_ports_are_counted_per_protocol(self):
        rows = [event(0), event(10), event(20, Proto="icmp", Dport=""), event(30, Dport="")]
        summary, _, _ = self.run_conversion(rows)
        self.assertEqual(summary["missing_dport_by_protocol_all_rows"], {"icmp": 1, "tcp": 1})
        self.assertEqual(summary["quality"]["protocol_filtered_rows"], 1)
        self.assertEqual(summary["quality"]["invalid_selected_rows"], 1)

    def test_no_inferred_utc_or_originator_and_no_labels_in_features(self):
        _, payload, _ = self.run_conversion([event(0, Dir="<?>"), event(10, Dir="<-")])
        self.assertEqual(payload["schema_version"], "1.1")
        flow = payload["flows"][0]
        self.assertEqual(flow["src_ip"], "192.0.2.1")
        self.assertEqual(flow["dst_port"], 80)
        self.assertEqual(flow["bytes_semantics"], "argus_src_bytes")
        self.assertFalse(flow["timestamps"][0].endswith("Z"))
        self.assertNotIn("Label", flow)
        self.assertNotIn("category", flow)

    def test_duplicates_and_zero_deltas_kept(self):
        summary, payload, _ = self.run_conversion([event(0), event(0), event(0)])
        self.assertEqual(payload["flows"][0]["event_count"], 3)
        self.assertEqual(payload["flows"][0]["time_deltas"], [0, 0])
        self.assertEqual(summary["quality"]["all_zero_interval_groups"], 1)

    def test_equal_timestamps_keep_csv_order(self):
        _, payload, _ = self.run_conversion([event(0, 200), event(0, 100)])
        self.assertEqual(payload["flows"][0]["bytes_sent"], [200, 100])

    def test_categories_never_become_beaconing(self):
        self.assertEqual(category("flow=From-Botnet-V42-TCP-CC16-HTTP"), "botnet")
        self.assertEqual(category("flow=To-Normal-V42-UDP-NTP-server"), "normal")
        self.assertEqual(category("flow=Background"), "background")
        self.assertEqual(category("flow=Normal-V42-HTTP-windowsupdate"), "normal")
        self.assertEqual(category("flow=New-Label"), "unknown")

    def test_bad_values_reported_without_changing_good_rows(self):
        rows = [event(0), event(10), event(20, Dport="0x0050"),
                event(30, SrcBytes="-1"), event(40, SrcAddr="not-an-ip")]
        summary, payload, _ = self.run_conversion(rows)
        self.assertEqual(summary["quality"]["invalid_selected_rows"], 3)
        self.assertEqual(payload["flows"][0]["event_count"], 2)
        self.assertEqual(len(summary["rejected_selected_row_examples"]), 3)

    def test_accounting_and_join_ids(self):
        summary, payload, labels = self.run_conversion([event(0), event(10), event(20, Dport="443")])
        q = summary["quality"]
        self.assertEqual(q["total_rows"], q["accepted_rows"] + q["invalid_selected_rows"] + q["protocol_filtered_rows"])
        self.assertEqual(q["accepted_rows"], q["exported_rows"] + q["short_group_rows"])
        self.assertEqual([f["flow_id"] for f in payload["flows"]], [a["flow_id"] for a in labels["labels"]])
        self.assertEqual(summary["run_id"], payload["run_id"])
        self.assertEqual(summary["run_id"], labels["run_id"])

    def test_all_short_is_valid_empty_bootstrap_export(self):
        summary, payload, _ = self.run_conversion([event(0)], min_events=5)
        self.assertEqual(payload["flows"], [])
        self.assertEqual(summary["quality"]["short_group_rows"], 1)

    def test_invalid_header_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.binetflow"
            source.write_text("wrong,header\na,b\n")
            with self.assertRaisesRegex(ValueError, "header"):
                convert(source, Path(directory) / "out")

    def test_no_valid_selected_rows_stops(self):
        with self.assertRaisesRegex(ValueError, "No valid selected"):
            self.run_conversion([event(0, Proto="udp")])


if __name__ == "__main__":
    unittest.main()
