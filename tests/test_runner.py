import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.runner import PROJECT_ROOT, main


class RunnerTests(unittest.TestCase):
    def test_model_cli_writes_named_score_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {
                "schema_version": "1.0",
                "flows": [{
                    "flow_id": "sample|test",
                    "event_count": 8,
                    "time_deltas": [1.0, 1.0, 2.0, 20.0, 20.0, 2.0, 1.0],
                    "bytes_sent": [100, 105, 110, 900, 920, 115, 108, 102],
                    "timestamps": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:01Z",
                        "2026-01-01T00:00:02Z",
                        "2026-01-01T00:00:04Z",
                        "2026-01-01T00:00:24Z",
                        "2026-01-01T00:00:44Z",
                        "2026-01-01T00:00:46Z",
                        "2026-01-01T00:00:47Z",
                    ],
                }],
            }
            processed = root / "flows.json"
            processed.write_text(json.dumps(payload), encoding="utf-8")
            config = {
                "dataset_id": "test",
                "input_csv": str(root / "unused.csv"),
                "processed_json": str(processed),
                "scores_json": str(root / "baseline.json"),
                "model_scores_dir": str(root / "model_scores"),
                "baseline": {"min_events": 5},
                "hmm": {"min_events": 5, "n_states": 2, "n_iter": 10, "random_seed": 42, "n_init": 1},
                "ct_hmm": {"min_events": 5, "n_states": 2, "n_iter": 10, "random_seed": 42, "n_init": 1, "tolerance": 0.00001},
                "tsd": {"mode": "event", "period": 3, "min_events": 5, "z_threshold": 3.0},
                "ensemble": {"state_model": "ct_hmm", "features": ["time_deltas", "bytes_sent"], "partial_policy": "strict"},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["model", "--name", "ensemble", "--config", str(config_path)])

            self.assertEqual(code, 0)
            self.assertTrue((root / "model_scores" / "ensemble.json").exists())

    def test_demo_creates_real_outputs_without_labels_or_mock_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "dataset_id": "sample",
                "input_csv": str(PROJECT_ROOT / "data/sample/connections.csv"),
                "processed_json": str(root / "flows.json"),
                "scores_json": str(root / "scores.json"),
                "baseline": {"min_events": 5},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["demo", "--config", str(config_path)])
            self.assertEqual(code, 0)
            flows = json.loads((root / "flows.json").read_text(encoding="utf-8"))
            scores = json.loads((root / "scores.json").read_text(encoding="utf-8"))["scores"]
            self.assertEqual(len(flows["flows"]), 2)
            self.assertEqual(len(scores), 2)
            self.assertEqual(sum(row["status"] == "ok" for row in scores), 1)
            self.assertTrue(all("label" not in flow for flow in flows["flows"]))
            self.assertTrue(all("prediction" not in row for row in scores))

    def test_bad_input_returns_error_without_creating_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_csv = root / "bad.csv"
            bad_csv.write_text("timestamp,src_ip\n", encoding="utf-8")
            config = {
                "dataset_id": "test", "input_csv": str(bad_csv),
                "processed_json": str(root / "flows.json"),
                "scores_json": str(root / "scores.json"),
                "baseline": {"min_events": 5},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["demo", "--config", str(config_path)])
            self.assertEqual(code, 2)
            self.assertFalse((root / "flows.json").exists())
            self.assertFalse((root / "scores.json").exists())
