# Baseline độ đều thời gian trên CTU-13 Scenario 1 — Thành Phát

## Chạy lại

Từ thư mục gốc repository, với `flows.json` và `labels.json` đã được tạo theo `docs/ctu13-contract.md`:

```bash
python -m src.analysis.run_ctu13_baseline
```

Lệnh đọc `data/processed/ctu13/scenario-01-tcp/flows.json` **schema 1.1** và lưu điểm cho toàn bộ nhóm tại `outputs/scores/ctu13-scenario01-timing-baseline.json`. Sau khi chấm xong, lệnh ghép `labels.json` theo `flow_id` để xuất `outputs/ctu13-scenario01-timing-baseline-ranking.csv`. Nhãn không tham gia tính điểm hoặc chọn nhóm chấm. Hai đầu vào phải cùng `run_id`; mã nhóm phải duy nhất và khớp. Mặc định `min_events=5`, phù hợp bản dữ liệu bootstrap đã xuất; có thể truyền `--min-events` để thử nghiệm riêng.

## Điểm và cách xếp hạng

Script dùng trực tiếp `src.baselines.statistical.score_flow`: với N bản ghi có N−1 khoảng thời gian, tính `CV = độ lệch chuẩn tổng thể / trung bình khoảng thời gian`, rồi `score = 1 / (1 + CV)`, làm tròn sáu chữ số thập phân như hàm gốc. Điểm lớn nghĩa **thời gian giữa các bản ghi flow đều hơn**. Điểm không phải xác suất độc hại và không có ngưỡng phân loại.

File JSON giữ `flow_id`, `method`, `event_count`, `score`, `status`, `reason` cho mọi nhóm. Nếu không tính được, `score=null` và `reason` ghi lý do. CSV phân tích có thêm `rank`, `category`, `cc_annotated_rows`; các nhóm `ok` xếp điểm giảm dần, điểm bằng nhau xếp `flow_id` tăng dần. Nhóm không có điểm được giữ ở cuối CSV, không có hạng. Do điểm được làm tròn sáu chữ số, nhiều nhóm có thể cùng điểm; hạng dưới đây theo đúng quy tắc sắp xếp đó.

## Kết quả chạy thực tế

| Chỉ tiêu | Số nhóm |
| --- | ---: |
| Nhóm đầu vào | 11.247 |
| Bản ghi điểm / dòng bảng xếp hạng | 11.247 / 11.247 |
| `ok` | 11.247 |
| `skipped` | 0 |
| `error` | 0 |

Các bảng hiển thị nhóm dưới dạng `src_ip → dst_ip:dst_port/protocol` để giữ đúng cấu trúc bảng Markdown. `flow_id` đầy đủ vẫn nằm trong JSON điểm và CSV xếp hạng; cách hiển thị không ảnh hưởng điểm hay thứ tự.

### Top 20 theo điểm

| Hạng | Nhóm | event_count | score | status | category | cc_annotated_rows |
| ---: | --- | ---: | ---: | --- | --- | ---: |
| 1 | 147.32.84.103 → 111.221.96.179:51791/tcp | 7 | 0.999999 | ok | background | 0 |
| 2 | 147.32.84.131 → 50.17.203.200:81/tcp | 6 | 0.999999 | ok | background | 0 |
| 3 | 147.32.84.164 → 50.17.203.200:81/tcp | 6 | 0.999999 | ok | normal | 0 |
| 4 | 147.32.84.164 → 74.125.232.216:443/tcp | 7 | 0.999999 | ok | normal | 0 |
| 5 | 147.32.84.166 → 174.142.248.155:5222/tcp | 6 | 0.999999 | ok | background | 0 |
| 6 | 147.32.84.184 → 195.113.232.75:80/tcp | 12 | 0.999999 | ok | background | 0 |
| 7 | 147.32.84.59 → 205.188.10.245:443/tcp | 5 | 0.999999 | ok | background | 0 |
| 8 | 147.32.84.73 → 113.161.71.62:38217/tcp | 6 | 0.999999 | ok | background | 0 |
| 9 | 147.32.85.2 → 205.188.11.58:5190/tcp | 5 | 0.999999 | ok | background | 0 |
| 10 | 147.32.85.63 → 137.226.34.42:80/tcp | 6 | 0.999999 | ok | background | 0 |
| 11 | 147.32.85.63 → 194.0.168.181:80/tcp | 6 | 0.999999 | ok | background | 0 |
| 12 | 147.32.86.121 → 147.228.52.22:1713/tcp | 5 | 0.999999 | ok | background | 0 |
| 13 | 147.32.86.147 → 147.228.52.22:1713/tcp | 6 | 0.999999 | ok | background | 0 |
| 14 | 147.32.86.84 → 74.125.39.125:5222/tcp | 6 | 0.999999 | ok | background | 0 |
| 15 | 147.32.87.3 → 147.32.86.23:1039/tcp | 5 | 0.999999 | ok | background | 0 |
| 16 | 147.32.87.48 → 147.32.80.13:3128/tcp | 6 | 0.999999 | ok | background | 0 |
| 17 | 147.32.87.51 → 147.32.192.25:443/tcp | 6 | 0.999999 | ok | background | 0 |
| 18 | 193.170.134.208 → 147.32.84.130:5222/tcp | 7 | 0.999999 | ok | background | 0 |
| 19 | 64.12.73.134 → 147.32.84.181:49932/tcp | 7 | 0.999999 | ok | background | 0 |
| 20 | 147.32.85.42 → 88.86.102.50:5222/tcp | 7 | 0.999998 | ok | background | 0 |

Trong top 20 có **19 nhóm dưới 10 bản ghi** (chỉ nhóm hạng 6 có 12 bản ghi). Điểm rất cao của các nhóm ngắn cần được đọc cùng độ dài chuỗi.

### Bảy nhóm có ít nhất một bản ghi gắn CC+số

| Hạng | Nhóm | event_count | score | status | category | cc_annotated_rows |
| ---: | --- | ---: | ---: | --- | --- | ---: |
| 952 | 147.32.84.165 → 222.88.205.195:443/tcp | 21 | 0.839341 | ok | botnet | 11 |
| 1.727 | 147.32.84.165 → 31.192.109.167:80/tcp | 53 | 0.638593 | ok | botnet | 53 |
| 2.827 | 147.32.84.165 → 213.246.53.125:5296/tcp | 9 | 0.525442 | ok | botnet | 9 |
| 2.831 | 147.32.84.165 → 61.17.216.4:6667/tcp | 5 | 0.525337 | ok | botnet | 5 |
| 2.963 | 147.32.84.165 → 61.167.116.133:6667/tcp | 5 | 0.513629 | ok | botnet | 5 |
| 7.452 | 147.32.84.165 → 173.192.170.88:80/tcp | 266 | 0.331751 | ok | botnet | 221 |
| 8.900 | 147.32.84.165 → 60.190.223.75:888/tcp | 10 | 0.278548 | ok | botnet | 10 |

Cả bảy nhóm này có `category=botnet` theo nhãn CTU-13. `cc_annotated_rows` chỉ là số bản ghi mang token CC+số, không phải số beacon đã xác minh.

### Ba nhóm đã vẽ trong tuần 2

| Hạng | Nhóm | event_count | score | status | category | cc_annotated_rows |
| ---: | --- | ---: | ---: | --- | --- | ---: |
| 1.727 | 147.32.84.165 → 31.192.109.167:80/tcp | 53 | 0.638593 | ok | botnet | 53 |
| 7.452 | 147.32.84.165 → 173.192.170.88:80/tcp | 266 | 0.331751 | ok | botnet | 221 |
| 11.038 | 147.32.84.164 → 194.79.52.199:80/tcp | 53 | 0.138733 | ok | normal | 0 |

Các biểu đồ tương ứng nằm trong `outputs/figures/ctu13-scenario01/`; xem `docs/data-exploration-week-02.md`. Cả ba nhóm đều có trạng thái `ok`. Đối chiếu CSV thống kê đã xuất ở tuần 2 với `score = 1/(1+CV)` (làm tròn sáu chữ số):

| Nhóm | CV | 1/(1+CV) | score trong CSV xếp hạng | Khớp |
| --- | ---: | ---: | ---: | --- |
| 147.32.84.165 → 31.192.109.167:80/tcp | 0.5659427609839722 | 0.638593 | 0.638593 | Có |
| 147.32.84.165 → 173.192.170.88:80/tcp | 2.014306862273611 | 0.331751 | 0.331751 | Có |
| 147.32.84.164 → 194.79.52.199:80/tcp | 6.208091414931801 | 0.138733 | 0.138733 | Có |

## Giới hạn diễn giải

Baseline đo **độ đều đặn của thời điểm các bản ghi flow Argus**. Nó không kết luận beaconing, C2 hay mã độc. Nhãn CC chưa phải ground truth beaconing; Background không mặc định là lành tính, và nhóm Botnet không đồng nghĩa mọi bản ghi là beacon. Top 20 có cả nhóm Normal và Background, cho thấy chỉ riêng điểm đều đặn không đủ để phân loại. Các nhóm rất ngắn cũng có thể đạt điểm gần 1, nên độ dài chuỗi cần được xem khi phân tích.

Đây là **kết quả phát triển trên Scenario 1**, chưa phải đánh giá trên tập kiểm tra độc lập. Chưa đặt ngưỡng hoặc tính Precision, Recall, F1 vì chưa chốt nhãn beaconing và cách chia tập.
