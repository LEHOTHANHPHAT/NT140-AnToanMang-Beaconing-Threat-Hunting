# Hướng dẫn demo baseline trên dữ liệu mô phỏng

## 1. Mục tiêu và phạm vi

Demo khoảng 3–5 phút để trình bày luồng: dữ liệu mô phỏng → điểm baseline → chọn ngưỡng trên dev → đánh giá trên test → phân tích lỗi.

Đây là đánh giá hành vi thời gian theo định nghĩa của bộ sinh, chưa phải đánh giá phát hiện mã độc. Phần mô hình HMM/CT-HMM, TSD và kết hợp chưa nằm trong demo này.

## 2. Chuẩn bị trước buổi demo

- Mở terminal Linux/WSL tại thư mục gốc repo `beaconing-threat-hunting`, kích hoạt môi trường Python đang dùng.
- Mở sẵn VS Code, dữ liệu dev, file ngưỡng và kết quả test.
- Dùng các tệp dữ liệu đã tạo; không sinh lại hoặc chỉnh dữ liệu trong buổi demo.
- Chạy ba bài kiểm tra chỉ số và thử bốn lệnh bên dưới trước buổi báo cáo.
- Kiểm tra thư mục `outputs/demo-synthetic-v1/` chưa chứa kết quả cần giữ: các lệnh sẽ ghi đè đầu ra cùng tên. Nếu cần giữ lần cũ, đổi đồng bộ tên thư mục cho lần demo mới.

Kiểm tra chỉ số:

```bash
python3 -m unittest discover -s tests/evaluation -p "test_synthetic_metrics.py" -v
```

Kỳ vọng: `Ran 3 tests` và `OK`. Các test kiểm tra hàm tính chỉ số, không chứng minh toàn bộ hệ thống hoặc mô hình chính xác.

Ghi lại phiên bản code khi chuẩn bị báo cáo:

```bash
git rev-parse HEAD
git status --short
```

## 3. Dữ liệu và cách tính

Mỗi tập dev/test có 80 nhóm; mỗi nhóm có 50 sự kiện và 49 khoảng cách. Dev dùng seed 100–119, test dùng seed 200–219.

| Mẫu | Số nhóm mỗi tập | Quy luật sinh | Nhãn |
|---|---:|---|---:|
| regular | 20 | Khoảng cách luôn 60 giây | 1 |
| jitter | 20 | Khoảng cách ngẫu nhiên đều từ 48–72 giây | 1 |
| random_arrivals | 20 | Khoảng cách phân phối mũ, trung bình lý thuyết 60 giây | 0 |
| bursty | 20 | 8 khoảng ngắn 1–5 giây, rồi khoảng nghỉ 300–600 giây | 0 |

Nhãn 1 là các mẫu được định nghĩa có nhịp khoảng cách gần cố định; nhãn 0 là các mẫu đối chiếu theo thiết kế này. Bursty vẫn có cấu trúc theo cụm, không phải hoàn toàn không có cấu trúc thời gian. Byte nguồn được giữ ở 500 mỗi sự kiện; baseline hiện chỉ dùng khoảng cách thời gian.

Baseline: `CV = std(time_deltas) / mean(time_deltas)`, rồi `score = 1 / (1 + CV)`. Điểm cao thể hiện khoảng cách đều hơn, không phải xác suất mã độc. Đầu ra đang dùng sáu chữ số thập phân.

Nhãn lưu riêng trong `labels.csv`, chỉ ghép theo `flow_id` ở bước đánh giá. Không đưa nhãn, tên mẫu hoặc mã nhóm vào đặc trưng mô hình.

## 4. Kịch bản nói và thao tác

| Thời gian | Thao tác | Ý chính cần giải thích |
|---|---|---|
| 0:00–0:40 | Mở một nhóm trong `data/synthetic/evaluation-v1/dev/groups.json` | 50 thời điểm tạo 49 khoảng cách; baseline đo độ đều của các khoảng cách |
| 0:40–1:30 | Chạy bước A và B | Chấm điểm dev trước, sau đó mới đọc nhãn để chọn ngưỡng |
| 1:30–2:20 | Chạy bước C và D | Test dùng dữ liệu khác; áp dụng nguyên ngưỡng đã chọn |
| 2:20–3:20 | Mở hai file metrics và trích FN | Test nhận đúng 38 nhóm nhãn 1, bỏ sót 2, không có FP trong 40 nhóm nhãn 0 |
| 3:20–4:00 | Nêu giới hạn và phần tiếp theo | Bộ mô phỏng còn đơn giản; sẽ so sánh với mô hình chính trên dữ liệu thống nhất |

### Bước A — Chấm điểm 80 nhóm dev

```bash
python3 -m src.analysis.score_synthetic_evaluation \
  --input data/synthetic/evaluation-v1/dev/groups.json \
  --output outputs/demo-synthetic-v1/dev_scores.csv
```

Kỳ vọng: 80 nhóm, 80 `ok`.

Lời nói gợi ý: “Chương trình đọc chuỗi khoảng cách của từng nhóm và tính điểm baseline. Bước này chưa sử dụng nhãn thật.”

### Bước B — Chọn ngưỡng trên dev

```bash
python3 -m src.evaluation.evaluate_synthetic \
  --scores outputs/demo-synthetic-v1/dev_scores.csv \
  --labels data/synthetic/evaluation-v1/dev/labels.csv \
  --out-dir outputs/demo-synthetic-v1/dev_evaluation \
  --select
```

Quy tắc chọn: F1 cao nhất → FPR thấp nhất → ngưỡng cao nhất. Quy tắc dự đoán: `score >= threshold` là nhãn 1.

Kỳ vọng: ngưỡng `0.887145`; TP=40, FP=0, FN=0, TN=40.

Mở `outputs/demo-synthetic-v1/dev_evaluation/selected_threshold.json`.

Lời nói gợi ý: “Em dùng dev để chọn ranh giới phân loại và lưu nó vào file. Ngưỡng này là kết quả thử nghiệm của baseline, không phải ngưỡng lấy từ bài báo.”

### Bước C — Chấm điểm 80 nhóm test

```bash
python3 -m src.analysis.score_synthetic_evaluation \
  --input data/synthetic/evaluation-v1/test/groups.json \
  --output outputs/demo-synthetic-v1/test_scores.csv
```

Kỳ vọng: 80 nhóm, 80 `ok`. Dev và test đều có 80 nhóm nhưng khác mã nhóm và seed; không đổi tên hoặc sao chép file điểm dev thành test.

### Bước D — Đánh giá test bằng ngưỡng đã lưu

```bash
python3 -m src.evaluation.evaluate_synthetic \
  --scores outputs/demo-synthetic-v1/test_scores.csv \
  --labels data/synthetic/evaluation-v1/test/labels.csv \
  --out-dir outputs/demo-synthetic-v1/test_evaluation \
  --threshold-file outputs/demo-synthetic-v1/dev_evaluation/selected_threshold.json
```

Lời nói gợi ý: “Điểm test được ghép với nhãn test. Chỉ ngưỡng được lấy từ dev, không chọn lại ngưỡng trên test.”

## 5. Kết quả dự kiến và cách giải thích

| Đại lượng | Dev | Test |
|---|---:|---:|
| Ngưỡng | 0.887145 | 0.887145 |
| TP | 40 | 38 |
| FP | 0 | 0 |
| FN | 0 | 2 |
| TN | 40 | 40 |
| Precision | 1.0 | 1.0 |
| Recall | 1.0 | 0.95 |
| F1 | 1.0 | 0.9743589743589743 |
| FPR | 0.0 | 0.0 |

- Precision: trong các nhóm được dự đoán nhãn 1, bao nhiêu nhóm đúng.
- Recall: trong 40 nhóm nhãn 1, tìm được 38 nhóm, tức 95%.
- F1: tổng hợp Precision và Recall, khoảng 97,44% trên test.
- FPR: không có nhóm nào trong 40 nhóm nhãn 0 bị dự đoán thành 1. Không suy rộng thành không bao giờ báo nhầm.

Các file nên mở:

```text
outputs/demo-synthetic-v1/dev_evaluation/metrics.csv
outputs/demo-synthetic-v1/test_evaluation/metrics.csv
outputs/demo-synthetic-v1/test_evaluation/predictions.csv
outputs/demo-synthetic-v1/test_evaluation/metrics_by_pattern.csv
```

## 6. Trích và giải thích hai trường hợp bỏ sót

```bash
python3 - <<'PY'
import csv

path = "outputs/demo-synthetic-v1/test_evaluation/predictions.csv"
with open(path, newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        if row["outcome"] == "FN":
            print(row["flow_id"], row["pattern"], row["score"])
PY
```

| Mã nhóm | Mẫu | Điểm | Thấp hơn ngưỡng |
|---|---|---:|---:|
| synthetic-eval-v1\|test\|sample-208-1 | jitter | 0.886490 | 0.000655 |
| synthetic-eval-v1\|test\|sample-216-1 | jitter | 0.880853 | 0.006292 |

Lời nói gợi ý: “Hai nhóm đều được sinh theo nhịp có dao động, nhưng CV của mẫu làm điểm thấp hơn ranh giới. Nhóm không chỉnh ngưỡng sau khi xem lỗi test.”

## 7. Giới hạn và phần bàn giao

- Kết quả là nhận biết mẫu thời gian mô phỏng, không phải F1 phát hiện mã độc.
- Dev/test dùng cùng họ quy luật sinh; khác seed không đồng nghĩa khác môi trường mạng.
- Các nhóm regular trùng đặc trưng; 20 nhóm không phải 20 bằng chứng độc lập.
- Byte giữ hằng; thí nghiệm chưa kiểm tra đóng góp của biến động byte.
- Không tự áp ngưỡng synthetic này sang CTU-13.
- Kết quả test và hai FN đã được xem. Nếu dùng chúng để chỉnh mô hình, coi tập đó là dữ liệu phát triển bổ sung và dùng tập kiểm tra cuối mới.
- Khi người B có mô hình, dùng cùng định dạng nhóm, giữ flow_id, báo ok/skipped/error và chọn ngưỡng riêng trên dev. So sánh chất lượng cùng độ bao phủ; chưa có bằng chứng mô hình chính tốt hơn baseline.
