# Bàn giao kỹ thuật từ Thành Phát Huy Phát

## Tình trạng phần A

| Phần việc | Tình trạng và bằng chứng |
| --- | --- |
| CSV mẫu, tiền xử lý và hợp đồng dữ liệu | Đã có [bộ đọc/gom nhóm](../src/data/prepare.py), [test dữ liệu](../tests/data/test_prepare.py), [hợp đồng](data-contract.md). |
| CTU-13 Scenario 1 TCP | Đã có [bộ chuyển](../src/data/prepare_ctu13.py), [test adapter](../tests/test_ctu13_adapter.py), [flows](../data/processed/ctu13/scenario-01-tcp/flows.json), [labels](../data/processed/ctu13/scenario-01-tcp/labels.json) và [summary](../data/processed/ctu13/scenario-01-tcp/summary.json). Bộ đã xuất 11.247 nhóm sau lọc `min_events=5`; kiểm tra trực tiếp thấy `flow_id` duy nhất và khớp giữa flows/labels/scores/ranking. |
| Khảo sát ba nhóm | Có [script vẽ](../src/analysis/plot_flows.py), [thống kê](../outputs/ctu13-scenario01-flow-statistics.csv) và [nhận xét](data-exploration-week-02.md). Chỉ là nhóm minh họa. |
| Baseline CTU-13 | [Hàm CV](../src/baselines/statistical.py), [lệnh chấm](../src/analysis/run_ctu13_baseline.py), [JSON điểm](../outputs/scores/ctu13-scenario01-timing-baseline.json), [CSV xếp hạng](../outputs/ctu13-scenario01-timing-baseline-ranking.csv): 11.247 ok, 0 skipped/error. [Phân tích A/B/C](../outputs/baseline_thresholds/summary.csv) lọc độ dài nhưng không đổi điểm. Chi tiết ở [nhận xét baseline](baseline-analysis.md). |
| Synthetic smoke/grid/evaluation | Có code sinh, chấm và kết quả lưu; smoke 5/5 khớp tham chiếu với sai số phù hợp; grid 200/200 ok; evaluation dev 40/0/0/40, test 38/0/2/40 ở ngưỡng 0,887145. Các file synthetic chưa được Git theo dõi và chưa có nhật ký chạy đầy đủ. |
| Bộ đánh giá tổng quát | [metrics.py](../src/evaluation/metrics.py) vẫn `NotImplementedError`. [evaluate_synthetic.py](../src/evaluation/evaluate_synthetic.py) chỉ là bộ đánh giá chuyên cho nhãn periodic synthetic. Chưa có bộ chỉ số CTU-13 vì chưa chốt ground truth beaconing. |
| Lab, tập kiểm tra thật, báo cáo cuối | [Lab](../lab/README.md) mới có hướng dẫn, chưa có mã client/server; chưa có CTU-13 test độc lập hoặc kết quả phát hiện trên dữ liệu thật. [Báo cáo tổng](../reports/report.md) còn dạng mẫu. |

## Bảng file bàn giao

| Đường dẫn | Nội dung | Người B sử dụng |
| --- | --- | --- |
| [data-contract.md](data-contract.md), [ctu13-contract.md](ctu13-contract.md) | Schema, ý nghĩa trường, ranh giới nhóm/nhãn | Xác nhận loader, feature, điều kiện chuỗi ngắn và khoảng cách 0. |
| [flows.json](../data/processed/ctu13/scenario-01-tcp/flows.json), [summary.json](../data/processed/ctu13/scenario-01-tcp/summary.json) | Chuỗi CTU-13 schema 1.1; SHA-256, nguồn và chất lượng | Phát triển mô hình trên Scenario 1; đối chiếu `run_id`, SHA-256 và điều kiện dữ liệu. File lớn được tạo tại máy, không mặc định có trên bản clone. |
| [labels.json](../data/processed/ctu13/scenario-01-tcp/labels.json) | Category, nhãn gốc, số bản ghi có CC, direction | **Chỉ** ghép sau khi đã chấm điểm để phân tích; không nạp vào mô hình. |
| [statistical.py](../src/baselines/statistical.py), [run_ctu13_baseline.py](../src/analysis/run_ctu13_baseline.py) | Hàm tính điểm và lệnh CTU-13 riêng | So sánh baseline với mô hình B; không dùng `src.runner baseline` schema 1.0 cho CTU-13. |
| [JSON baseline](../outputs/scores/ctu13-scenario01-timing-baseline.json), [CSV xếp hạng](../outputs/ctu13-scenario01-timing-baseline-ranking.csv) | Điểm toàn bộ nhóm, trạng thái, hạng, nhãn phân tích | So score theo cùng `flow_id`; CSV có nhãn, JSON điểm không có nhãn. |
| [summary A/B/C](../outputs/baseline_thresholds/summary.csv), [CC tracking](../outputs/baseline_thresholds/cc_tracking.csv) | Ảnh hưởng ngưỡng số bản ghi 5/10/20 đến danh sách | Chốt tập đủ điều kiện chung trước khi so phương pháp; không hiểu hạng tốt hơn là điểm tốt hơn. |
| [smoke groups](../data/synthetic/smoke-v1/groups.json), [reference](../data/synthetic/smoke-v1/reference_stats.csv), [comparison](../outputs/synthetic-smoke-v1/comparison.csv) | Năm mẫu kiểm tra phép tính | Thử loader/mô hình và xem giới hạn: regular và legitimate_periodic cùng điểm. |
| [grid config](../data/synthetic/grid-v1/generation_config.json), [summary grid](../outputs/synthetic-grid-v1/summary.csv) | Ma trận 4 độ dài × 5 jitter × 10 seed | Kiểm tra độ ổn định theo độ dài/jitter; seed cùng số giữa cấu hình là so sánh có liên hệ. |
| [evaluation config](../data/synthetic/evaluation-v1/generation_config.json), [dev groups](../data/synthetic/evaluation-v1/dev/groups.json), [test groups](../data/synthetic/evaluation-v1/test/groups.json) | Bốn mẫu, mỗi split 80 nhóm; nhãn ở `labels.csv` cùng thư mục | Dùng đúng cùng tập khi so phương pháp; tránh tên mẫu/seed/split làm feature. |
| [ngưỡng dev](../outputs/synthetic-evaluation-v1/dev_evaluation/selected_threshold.json), [metrics test](../outputs/synthetic-evaluation-v1/test_evaluation/metrics.csv), [predictions test](../outputs/synthetic-evaluation-v1/test_evaluation/predictions.csv) | Ngưỡng và kết quả baseline synthetic đã lưu | Tham chiếu phép đánh giá và hai FN đã biết; không điều chỉnh theo test rồi báo test này độc lập. |
| [experiment-plan.md](experiment-plan.md), [mẫu run](../experiments/run-template.md) | Phạm vi đánh giá, nhật ký và tái lập | Chốt mục tiêu nhãn, split, seed, cấu hình và kết quả cuối với người A. |

## Lệnh CLI đã kiểm tra về cú pháp

Các cờ của các lệnh có tham số dưới đây đã được đối chiếu bằng `--help`; lệnh không có cờ được đối chiếu trong `main()` của script. **Chưa chạy lại thực nghiệm trong lần bàn giao này.** Chạy từ thư mục gốc repo. Các lệnh dùng `outputs/recheck-*` để tránh ghi đè kết quả cũ; khi muốn sinh lại dữ liệu, một số bộ sinh có đường dẫn cố định nên cần dùng bản sao workspace hoặc lưu riêng file hiện tại trước.

```powershell
python -m src.analysis.run_ctu13_baseline --data-dir data/processed/ctu13/scenario-01-tcp --scores-out outputs/recheck-ctu13/scores.json --ranking-out outputs/recheck-ctu13/ranking.csv --min-events 5
python -m src.analyze_baseline_thresholds --input outputs/ctu13-scenario01-timing-baseline-ranking.csv --out-dir outputs/recheck-thresholds
python -m src.generate_synthetic_smoke --out-dir data/synthetic/recheck-smoke --seed 42
python -m src.analysis.run_synthetic_baseline --input data/synthetic/smoke-v1/groups.json --reference data/synthetic/smoke-v1/reference_stats.csv --out-dir outputs/recheck-smoke --min-events 5
python -m src.score_synthetic_evaluation --input data/synthetic/evaluation-v1/dev/groups.json --output outputs/recheck-evaluation/dev_scores.csv
python -m src.evaluation.evaluate_synthetic --scores outputs/synthetic-evaluation-v1/dev_scores.csv --labels data/synthetic/evaluation-v1/dev/labels.csv --out-dir outputs/recheck-evaluation/dev_evaluation --select
python -m src.score_synthetic_evaluation --input data/synthetic/evaluation-v1/test/groups.json --output outputs/recheck-evaluation/test_scores.csv
python -m src.evaluation.evaluate_synthetic --scores outputs/synthetic-evaluation-v1/test_scores.csv --labels data/synthetic/evaluation-v1/test/labels.csv --out-dir outputs/recheck-evaluation/test_evaluation --threshold-file outputs/synthetic-evaluation-v1/dev_evaluation/selected_threshold.json
```

Để tái tạo một chuỗi dev → test **từ điểm vừa chấm**, thay `--scores` dev/test bằng `outputs/recheck-evaluation/*_scores.csv` và `--threshold-file` test bằng `outputs/recheck-evaluation/dev_evaluation/selected_threshold.json`. [Grid script](../src/analysis/run_synthetic_grid.py) chạy bằng `python -m src.analysis.run_synthetic_grid` nhưng hiện ghi cố định vào `data/synthetic/grid-v1/` và `outputs/synthetic-grid-v1/`; không chạy trong workspace này nếu cần giữ nguyên kết quả. [Bộ sinh evaluation](../src/generate_synthetic_evaluation.py) chạy bằng `python -m src.generate_synthetic_evaluation` và cũng ghi cố định vào `data/synthetic/evaluation-v1/`. [Bộ chuyển CTU-13](../src/data/prepare_ctu13.py) có lệnh và tham số nguồn trong [START_HERE_WEEK2.md](../START_HERE_WEEK2.md); dành ổ đĩa đủ lớn và xuất sang đường dẫn mới nếu tái tạo.

## Hợp đồng mô hình người B cần nhận

CTU-13 `flows.json` schema 1.1 có `flow_id = dataset_id|src_ip|dst_ip|dst_port|protocol`, `event_count=N`, `relative_times_seconds` và `bytes_sent` dài **N**, `time_deltas` dài **N−1**. Timestamp CTU-13 là đồng hồ nguồn chưa xác minh múi giờ; `bytes_semantics=argus_src_bytes`, không tự nhận phía nguồn là client/initiator. Nếu quan sát byte theo sự kiện, dùng cặp `relative_times_seconds[i]`, `bytes_sent[i]`; nếu quan sát theo khoảng cách, phải thống nhất căn chỉnh N−1 khoảng với N byte và ghi rõ trong phương pháp. Giữ ranh giới giữa các nhóm khi học từ nhiều chuỗi. Không dùng `flow_id`, IP, tên pattern, nhãn, seed, split hoặc metadata sinh làm feature.

Mỗi phương pháp trả ít nhất `flow_id`, `method`, `score`, `status`, `reason`; nên có `event_count` để kiểm tra đầu vào. Khi không tính được, `score=null`, `status=skipped/error` và `reason` rõ ràng. Nêu **chiều điểm**: cao hơn nghĩa là gì; điểm chưa hiệu chuẩn không phải xác suất độc hại. HMM thường và CT-HMM phải mang tên kết quả riêng; các hàm trong [hmm.py](../src/models/hmm.py), [ct_hmm.py](../src/models/ct_hmm.py), [tsd.py](../src/models/tsd.py), [ensemble.py](../src/models/ensemble.py) hiện vẫn `NotImplementedError`, nên chưa thể ghi là đã có kết quả mô hình B.

## Ghép nhãn và so sánh công bằng

1. Chấm **mọi nhóm đầu vào** trước; lưu điểm/trạng thái theo `flow_id`. Kiểm tra mã duy nhất, số đầu ra, `run_id` và không rò nhãn vào feature. Sau đó mới ghép `labels.json` hoặc CSV nhãn synthetic theo `flow_id`. Chỉ dùng `category`/`cc_annotated_rows` của CTU-13 cho khảo sát; cần ground truth phù hợp trước khi tính confusion matrix beaconing.
2. Cho baseline, HMM, CT-HMM, TSD và kết hợp điểm chạy trên **cùng tập nhóm**. Báo `ok/skipped/error` và tỷ lệ bao phủ riêng từng phương pháp; so điểm/chỉ số trên giao các nhóm `ok` đủ điều kiện, đồng thời công bố số nhóm bị loại. Không coi nhóm bị bỏ qua là âm tính.
3. Chốt mục tiêu nhãn và split trước: trên synthetic hiện có, nhãn 1 nghĩa mẫu `regular`/`jitter` do bộ sinh định nghĩa. Chọn **ngưỡng riêng cho từng phương pháp trên dev**, cố định cấu hình/ngưỡng rồi chạy test. Không dùng ngưỡng synthetic của baseline cho CTU-13 hoặc phương pháp khác mà chưa kiểm chứng.
4. Lưu nguồn dữ liệu/checksum, cấu hình feature, tham số, seed, commit hoặc bản mã, thời gian chạy, môi trường và output theo [mẫu run](../experiments/run-template.md). Báo cả lỗi điển hình, giới hạn nhãn và thay đổi sau khi xem test.

**Tính độc lập:** kết quả test synthetic và hai FN `sample-208-1`, `sample-216-1` đã được nhóm xem. Nếu người B dùng chúng để sửa mô hình, đặc trưng hoặc ngưỡng, phải ghi nhận test này đã thành dữ liệu phát triển và tạo **tập kiểm tra mới** cho đánh giá cuối. Không gọi lại nó là tập kiểm tra độc lập.

## Những việc cần thống nhất giữa A và B

- Chọn mục tiêu cuối: nhịp tuần hoàn do bộ sinh, C2, botnet hay beaconing; quy định nhãn nào hợp lệ, xử lý Background/mixed/unknown và nhóm có token CC.
- Chọn scenario hoặc capture mới làm kiểm tra độc lập với Scenario 1 phát triển; thống nhất số quan sát tối thiểu và chính sách khoảng cách 0/chuỗi ngắn cho từng mô hình.
- Xác nhận CT-HMM khả thi và thực sự dùng thời gian liên tục hay chỉ có HMM thường; thống nhất feature, chiều điểm, điều kiện mô hình `ok`, cách kết hợp điểm và tập nhóm chung.
- Chốt lịch ghi run log và đưa script/dữ liệu synthetic đang chưa theo dõi vào phiên bản tái lập trước khi viết báo cáo cuối.
