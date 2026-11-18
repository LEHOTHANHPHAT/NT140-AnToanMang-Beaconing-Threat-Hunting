# Nhận xét baseline độ đều thời gian — Thành Phát


## Mục tiêu, đơn vị dữ liệu và phép tính

Baseline xếp nhóm theo độ đều của thời điểm giao tiếp, không phân loại mã độc. Theo [hợp đồng dữ liệu](data-contract.md) và [quy ước CTU-13](ctu13-contract.md), nhóm CTU-13 là các **bản ghi flow Argus** chung `(SrcAddr, DstAddr, Dport, Proto)`; một bản ghi không phải packet hay HTTP request. `N` bản ghi có `N−1` giá trị `time_deltas` tính bằng giây. CTU-13 lưu `bytes_sent` từ `SrcBytes` với `bytes_semantics=argus_src_bytes`; không suy ra đó luôn là byte do client khởi tạo gửi. Baseline hiện chỉ dùng `event_count` và `time_deltas`, không dùng byte, IP, nhãn hay metadata sinh làm đặc trưng.

Trong [hàm `score_flow`](../src/baselines/statistical.py), `mean = fmean(time_deltas)`, `std = pstdev(time_deltas)` là **độ lệch chuẩn tổng thể**, `CV = std/mean`, rồi `score = round(1/(1+CV), 6)`. Chỉ điểm cuối được làm tròn sáu chữ số; điểm cao nghĩa nhịp các **bản ghi flow** đều hơn, không phải xác suất beaconing. Mặc định `min_events=5`; nếu nhóm ngắn hơn hoặc trung bình delta bằng 0 thì `status=skipped`, `score=null`, có `reason`. `event_count < 1`, độ dài delta sai, delta âm/không hữu hạn bị từ chối; [lệnh chạy CTU-13](../src/analysis/run_ctu13_baseline.py) ghi `status=error`, `score=null` và lý do cho lỗi có thể bắt được. Đầu ra giữ `flow_id`, `method`, `event_count`, `score`, `status`, `reason`.

Lệnh CTU-13 chấm **toàn bộ `flows.json` schema 1.1 trước khi đọc `labels.json`**; sau đó kiểm tra `run_id`, tính duy nhất và tập `flow_id`, rồi ghép nhãn chỉ cho [CSV xếp hạng](../outputs/ctu13-scenario01-timing-baseline-ranking.csv). Chỉ các dòng `ok` có hạng, xếp theo **điểm đã lưu giảm dần**, đồng điểm sắp `flow_id` tăng dần; dòng skipped/error ở cuối và không có hạng. Bảng A/B/C của [script phân tích số bản ghi](../src/analyze_baseline_thresholds.py) lọc thêm `event_count` rồi xếp lại theo điểm **đầy đủ từ CSV**, đồng điểm dùng cùng quy tắc. Ngưỡng 10/20 ở đây là **điều kiện độ dài nhóm**, không phải ngưỡng phân loại.

## CTU-13 Scenario 1: kết quả đã xác nhận

[Dữ liệu CTU-13 đã xử lý](../data/processed/ctu13/scenario-01-tcp/flows.json), [nhãn](../data/processed/ctu13/scenario-01-tcp/labels.json), [JSON điểm](../outputs/scores/ctu13-scenario01-timing-baseline.json) và CSV xếp hạng đều có **11.247 mã nhóm duy nhất trùng nhau**; ba file JSON có `run_id` khớp. `source.sha256` ghi `be09f7f6a06beef0134152dc88bff85f0027db4affe07b3fbe956bbb49be5430`. JSON điểm ghi `ok=11.247`, `skipped=0`, `error=0`, `min_events=5`. Đây là tập phát triển Scenario 1 TCP, chưa có chia dev/test CTU-13 độc lập. [Báo cáo tuần 3](baseline-week-03.md) chứa top 20 A và điểm từng nhóm CC.

Đối chiếu [summary A/B/C](../outputs/baseline_thresholds/summary.csv), [ba CSV top 20](../outputs/baseline_thresholds/A_top20.csv), [B](../outputs/baseline_thresholds/B_top20.csv), [C](../outputs/baseline_thresholds/C_top20.csv):

| Danh sách | Điều kiện trên nhóm `ok` | Nhóm đủ điều kiện | Normal / Background / Botnet trong top 20 | Nhóm có CC còn lại |
| --- | --- | ---: | --- | ---: |
| A | Không lọc thêm số bản ghi | 11.247 | 2 / 18 / 0 | 7 |
| B | `event_count >= 10` | 5.585 | 0 / 20 / 0 | 4 |
| C | `event_count >= 20` | 3.009 | 0 / 20 / 0 | 3 |

Trong top 20 A, **19/20 nhóm có dưới 10 bản ghi**. Tăng điều kiện độ dài làm tập được xếp hạng nhỏ đi; hạng số học của một nhóm có thể nhỏ hơn mà **điểm của nó không đổi**. Cả ba top 20 không chứa nhóm nào trong bảy nhóm có token CC. Từ dữ liệu này không thể nói “Recall beaconing bằng 0”: CC chỉ là chú thích, Botnet không đồng nghĩa beaconing đã xác minh, và Background không mặc định là lành tính.

Đối chiếu [bảng theo dõi CC](../outputs/baseline_thresholds/cc_tracking.csv) với các bảng A/B/C (`—` là không đủ số bản ghi):

| Đích:cổng | N | Score | Hạng A | Hạng B | Hạng C |
| --- | ---: | ---: | ---: | ---: | ---: |
| 222.88.205.195:443 | 21 | 0.839341 | 952 | 134 | 87 |
| 31.192.109.167:80 | 53 | 0.638593 | 1.727 | 371 | 197 |
| 213.246.53.125:5296 | 9 | 0.525442 | 2.827 | — | — |
| 61.17.216.4:6667 | 5 | 0.525337 | 2.831 | — | — |
| 61.167.116.133:6667 | 5 | 0.513629 | 2.963 | — | — |
| 173.192.170.88:80 | 266 | 0.331751 | 7.452 | 2.433 | 1.143 |
| 60.190.223.75:888 | 10 | 0.278548 | 8.900 | 3.308 | — |

Hai nhóm top đầu được kiểm tra thêm trực tiếp trên [bản ghi gốc](../data/raw/ctu13/scenario-01/capture20110810.binetflow) và chuỗi đã xử lý. Normal `147.32.84.164 → 50.17.203.200:81/tcp` có 6 dòng, khoảng cách StartTime từ **3.600,019486 đến 3.600,026180 giây**; sáu cổng nguồn khác nhau, năm `Dur` khoảng 0,364 giây, dòng cuối `Dur=127,116692` giây. Background `147.32.84.184 → 195.113.232.75:80/tcp` có 12 dòng, khoảng cách từ **1.800,033568 đến 1.800,041457 giây**; 12 cổng nguồn khác nhau, `Dur` khoảng 500,071–500,096 giây và `SrcBytes=665` ở tất cả 12 dòng. **Suy luận:** các dòng phù hợp những lần giao tiếp riêng theo chu kỳ; chưa xác định ứng dụng hoặc mục đích độc hại. `Dur` là thời lượng từng bản ghi, khác với khoảng cách giữa hai `StartTime`.

## Synthetic smoke-v1: kiểm tra phép tính

[Bộ sinh smoke](../src/generate_synthetic_smoke.py) lưu 5 nhóm, mỗi nhóm 50 sự kiện và byte giả lập 500, tại [groups.json](../data/synthetic/smoke-v1/groups.json). [Bảng đối chiếu](../outputs/synthetic-smoke-v1/comparison.csv) ghi:

| Mẫu | Điểm baseline | Sai khác tuyệt đối so với tham chiếu |
| --- | ---: | ---: |
| regular | 1,000000 | 0 |
| jitter | 0,944137 | 0,0000000652234491 |
| rate_change | 0,751308 | 0,0000000446389564 |
| irregular | 0,633285 | 0,0000001749677780 |
| legitimate_periodic | 1,000000 | 0 |

Điểm tham chiếu trong [reference_stats.csv](../data/synthetic/smoke-v1/reference_stats.csv) không làm tròn sáu chữ số, còn baseline có làm tròn; vì thế đòi khớp với sai số `1e-9` sẽ thất bại với ba mẫu giữa. [Mã đối chiếu hiện tại](../src/analysis/run_synthetic_baseline.py) dùng `math.isclose(..., rel_tol=0.0, abs_tol=5e-7)` và cả năm dòng có `matches_reference=True`. `regular` và `legitimate_periodic` có cùng chuỗi thời gian và byte nên cùng điểm 1 dù metadata ngữ cảnh khác nhau. Đây là kiểm tra phép tính, không đo khả năng phát hiện mã độc.

## Synthetic grid-v1: độ nhạy theo jitter và chiều dài

[Bộ sinh grid](../src/analysis/run_synthetic_grid.py) đặt chu kỳ gốc 60 giây, N thuộc `{10,20,50,100}`, jitter đều trong ±`{0,5,10,20,40}%`, seed `0..9`, byte mỗi bản ghi 500. [Config](../data/synthetic/grid-v1/generation_config.json), [chi tiết](../outputs/synthetic-grid-v1/detail.csv) và [summary](../outputs/synthetic-grid-v1/summary.csv) xác nhận 200 nhóm, **200 ok**, không skipped/error. Mỗi ô dưới có 10 seed; giá trị là `score_mean` / `score_std_across_seeds` (làm tròn để trình bày):

| N | 0% | 5% | 10% | 20% | 40% |
| ---: | --- | --- | --- | --- | --- |
| 10 | 1,0000 / 0 | 0,9731 / 0,00417 | 0,9475 / 0,00787 | 0,8999 / 0,01421 | 0,8169 / 0,02450 |
| 20 | 1,0000 / 0 | 0,9729 / 0,00257 | 0,9472 / 0,00500 | 0,8994 / 0,00964 | 0,8165 / 0,01875 |
| 50 | 1,0000 / 0 | 0,9719 / 0,00189 | 0,9454 / 0,00364 | 0,8965 / 0,00681 | 0,8123 / 0,01252 |
| 100 | 1,0000 / 0 | 0,9717 / 0,00146 | 0,9450 / 0,00285 | 0,8959 / 0,00552 | 0,8119 / 0,01071 |

**Nhận xét từ bảng:** trong từng N, jitter tăng thì điểm trung bình giảm; ở từng mức jitter khác 0, độ lệch chuẩn điểm giữa 10 seed giảm khi N tăng. `score_mean` không tăng theo N trong bảng này, nên không suy ra nhiều sự kiện luôn làm điểm cao. `score_std_across_seeds` do `statistics.stdev` tính trên **10 điểm nhóm** (độ lệch chuẩn mẫu), khác `pstdev(time_deltas)` trong một nhóm dùng để tính CV. Bộ sinh khởi tạo lại `Random(seed)` cho mỗi cấu hình; cùng seed tạo so sánh có liên hệ, không phải mẫu độc lập giữa các cấu hình. Jitter 0% tạo chuỗi delta 60 giây giống nhau ở mọi seed, nên mười dòng mỗi N là lặp đặc trưng, không phải mười lần quan sát thời gian độc lập.

## Synthetic evaluation-v1: dev/test theo nhãn bộ sinh

[Bộ sinh evaluation](../src/generate_synthetic_evaluation.py) và [config](../data/synthetic/evaluation-v1/generation_config.json) tạo mỗi tập 80 nhóm, mỗi nhóm 50 sự kiện và byte 500: `regular` 20 nhóm nhãn 1, `jitter` đều 48–72 giây (±20% quanh 60) 20 nhóm nhãn 1; `random_arrivals` phân phối mũ trung bình lý thuyết 60 giây 20 nhóm nhãn 0; `bursty` gồm tám khoảng 1–5 giây rồi một khoảng 300–600 giây 20 nhóm nhãn 0 **theo định nghĩa bộ sinh**. Dev dùng seed 100–119, test 200–219. Đây là bài toán phân loại **kiểu thời gian giả lập**, không có nhãn mã độc thật. Dữ liệu nằm trong [dev](../data/synthetic/evaluation-v1/dev/groups.json) và [test](../data/synthetic/evaluation-v1/test/groups.json), nhãn ở CSV cùng thư mục.

[Bộ chấm](../src/score_synthetic_evaluation.py) chỉ đọc nhóm. [Bộ đánh giá](../src/evaluation/evaluate_synthetic.py) ghép nhãn theo `flow_id` sau khi chấm; chọn ngưỡng trên dev theo **F1 cao nhất → FPR thấp nhất → ngưỡng cao nhất**, với quy tắc `score >= threshold` dự đoán 1. [Ngưỡng đã lưu](../outputs/synthetic-evaluation-v1/dev_evaluation/selected_threshold.json) là **0,887145**; test dùng lại đúng ngưỡng này. [Metrics dev](../outputs/synthetic-evaluation-v1/dev_evaluation/metrics.csv), [metrics test](../outputs/synthetic-evaluation-v1/test_evaluation/metrics.csv) và predictions xác nhận:

| Tập | TP | FP | FN | TN | Precision | Recall | F1 | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dev | 40 | 0 | 0 | 40 | 1 | 1 | 1 | 0 |
| Test | 38 | 0 | 2 | 40 | 1 | 0,95 | 0,9743589743589743 | 0 |

[Predictions test](../outputs/synthetic-evaluation-v1/test_evaluation/predictions.csv) cho hai FN đều thuộc `jitter`: `synthetic-eval-v1|test|sample-208-1` có điểm **0,886490**, thấp hơn ngưỡng **0,000655**; `synthetic-eval-v1|test|sample-216-1` có điểm **0,880853**, thấp hơn **0,006292**. Hai số chênh tính từ ngưỡng đã lưu, không hạ ngưỡng sau khi nhìn test. Theo [metrics theo mẫu](../outputs/synthetic-evaluation-v1/test_evaluation/metrics_by_pattern.csv), `jitter` đạt 18 TP/2 FN; `regular` 20 TP, hai loại âm tính mỗi loại 20 TN. **Suy luận:** ngưỡng chọn trên dev không bao phủ mọi biến thiên của mẫu jitter test. FPR bằng 0 trên 40 nhóm âm tính giả lập không chứng minh sẽ không báo nhầm ngoài thực tế.

## Giới hạn và việc chưa xác minh

- Chưa có ground truth beaconing cho CTU-13 Scenario 1 hoặc tập kiểm tra CTU-13 độc lập; [kế hoạch thực nghiệm](experiment-plan.md) vẫn yêu cầu chốt phạm vi nhãn, chính sách Background/mixed và cách chia scenario. Không chuyển ngưỡng 0,887145 từ synthetic sang CTU-13 nếu chưa kiểm chứng.
- Kết quả test synthetic và hai FN **đã được nhóm xem**. Nếu từ đây điều chỉnh mô hình hoặc ngưỡng theo chúng, tập này thành dữ liệu phát triển; cần tập kiểm tra mới để đánh giá cuối.
- Điểm baseline chỉ dùng thời gian, không phân biệt ngữ cảnh ứng dụng hay phân tích nội dung/byte. Top 20 CTU-13 A có 19 nhóm dưới 10 bản ghi; số điểm gần 1 ở chuỗi ngắn cần thận trọng. Một bản ghi Argus có thể chịu ảnh hưởng cách collector xuất flow.
- Các file synthetic và script tương ứng hiện chưa được Git theo dõi trong working tree. Chưa thấy nhật ký chạy đầy đủ cho từng synthetic run (commit áp dụng cho file chưa theo dõi, thời gian chạy, môi trường, cấu hình/seed đã chốt) theo [mẫu nhật ký](../experiments/run-template.md); khả năng tái lập độc lập của toàn bộ kết quả chưa được xác nhận.

Baseline đã kiểm tra được phép tính, đáp ứng việc **xếp nhóm theo nhịp thời gian** và phân biệt các mẫu synthetic do nhóm định nghĩa trong điều kiện đã lưu. Nó **chưa chứng minh phát hiện beaconing hoặc mã độc trên mạng thật**. Để so sánh công bằng với HMM, CT-HMM, TSD và kết hợp điểm, cần chốt nhãn và tập kiểm tra độc lập, rồi báo cả độ bao phủ lẫn chỉ số trên cùng nhóm hợp lệ.
