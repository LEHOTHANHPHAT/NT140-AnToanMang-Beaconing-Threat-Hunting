import csv
import tempfile
import unittest
from pathlib import Path

from src.data.prepare import REQUIRED_FIELDS, prepare_csv

SAMPLE = Path(__file__).resolve().parents[2] / "data/sample/connections.csv"


class PrepareTests(unittest.TestCase):
    def test_groups_and_aligned_features(self):
        result = prepare_csv(SAMPLE)
        self.assertEqual(result["quality"]["event_count"], 8)
        self.assertEqual(result["quality"]["flow_count"], 2)
        first, second = result["flows"]
        self.assertEqual(first["time_deltas"], [60, 62, 59, 59])
        self.assertEqual(first["bytes_sent"], [120, 122, 119, 121, 120])
        self.assertEqual(second["time_deltas"], [15, 155])
        self.assertEqual(result["quality"]["naive_timestamps_assumed_utc"], 8)

    def test_reordering_distinct_timestamps_preserves_result(self):
        lines = SAMPLE.read_text(encoding="utf-8").splitlines()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / SAMPLE.name
            path.write_text("\n".join([lines[0], *reversed(lines[1:])]) + "\n", encoding="utf-8")
            self.assertEqual(prepare_csv(path), prepare_csv(SAMPLE))

    def test_invalid_ip_reports_csv_line(self):
        text = SAMPLE.read_text(encoding="utf-8").replace("192.168.1.10", "not-an-ip", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV line 2"):
                prepare_csv(path)

    def test_missing_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text("timestamp,src_ip\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Missing CSV columns"):
                prepare_csv(path)

    def test_duplicate_events_are_kept_and_reported(self):
        lines = SAMPLE.read_text(encoding="utf-8").splitlines()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.csv"
            path.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
            result = prepare_csv(path)
            self.assertEqual(result["quality"]["event_count"], 9)
            self.assertEqual(result["quality"]["exact_duplicate_events_kept"], 1)
            self.assertIn(0, result["flows"][0]["time_deltas"])

    def test_offsets_are_normalized_to_utc(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "offset.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(REQUIRED_FIELDS)
                writer.writerow(["2026-10-14T09:00:00+07:00", "10.0.0.1", "10.0.0.2", 80, "TCP", 1])
                writer.writerow(["2026-10-14T02:01:00Z", "10.0.0.1", "10.0.0.2", 80, "tcp", 2])
            result = prepare_csv(path)
            self.assertEqual(result["flows"][0]["time_deltas"], [60])
            self.assertEqual(result["flows"][0]["timestamps"][0], "2026-10-14T02:00:00Z")
            self.assertEqual(result["quality"]["naive_timestamps_assumed_utc"], 0)

    def test_empty_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text(",".join(REQUIRED_FIELDS) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no communication events"):
                prepare_csv(path)

    def test_negative_bytes_are_rejected(self):
        text = SAMPLE.read_text(encoding="utf-8").replace(",119", ",-119", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nonnegative"):
                prepare_csv(path)
