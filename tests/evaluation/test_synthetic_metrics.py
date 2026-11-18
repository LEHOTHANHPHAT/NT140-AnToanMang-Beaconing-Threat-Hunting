import unittest

from src.evaluation.evaluate_synthetic import calculate_metrics


class TestSyntheticMetrics(unittest.TestCase):
    def test_known_confusion_matrix(self):
        rows = [
            {"actual": 1, "score": 0.95},
            {"actual": 1, "score": 0.90},
            {"actual": 1, "score": 0.80},
            {"actual": 1, "score": 0.60},
            {"actual": 0, "score": 0.85},
            {"actual": 0, "score": 0.70},
            {"actual": 0, "score": 0.40},
            {"actual": 0, "score": 0.20},
        ]

        result = calculate_metrics(rows, threshold=0.8)

        self.assertEqual(result["tp"], 3)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["fn"], 1)
        self.assertEqual(result["tn"], 3)

        self.assertAlmostEqual(result["precision"], 0.75)
        self.assertAlmostEqual(result["recall"], 0.75)
        self.assertAlmostEqual(result["f1"], 0.75)
        self.assertAlmostEqual(result["fpr"], 0.25)

    def test_no_positive_predictions(self):
        rows = [
            {"actual": 1, "score": 0.2},
            {"actual": 0, "score": 0.1},
        ]

        result = calculate_metrics(rows, threshold=0.8)

        self.assertEqual(result["fn"], 1)
        self.assertEqual(result["tn"], 1)
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["f1"], 0.0)
        self.assertEqual(result["fpr"], 0.0)

    def test_no_negative_labels(self):
        rows = [
            {"actual": 1, "score": 0.9},
            {"actual": 1, "score": 0.7},
        ]

        result = calculate_metrics(rows, threshold=0.8)

        # Không có nhóm nhãn 0 nên FPR không xác định.
        self.assertIsNone(result["fpr"])
        self.assertEqual(result["tp"], 1)
        self.assertEqual(result["fn"], 1)


if __name__ == "__main__":
    unittest.main()