# Phương pháp và tình trạng triển khai

## Luồng xử lý

Đọc nguồn dữ liệu, kiểm tra ý nghĩa trường, gom nhóm, tạo chuỗi thời gian và byte, chấm điểm từng phương pháp, ghép nhãn đánh giá riêng, phân tích nhóm nghi vấn.

## Baseline hiện có

`src/baselines/statistical.py` đo độ đều của khoảng thời gian bằng hệ số biến thiên CV. Điểm là 1 chia cho 1 cộng CV, dùng độ lệch chuẩn tổng thể. Cần đủ số sự kiện và trung bình khoảng thời gian dương.

Phương pháp này do nhóm dùng làm mốc đơn giản. Điểm cao không phân biệt được dịch vụ hợp lệ định kỳ với giao tiếp độc hại. Chưa có ngưỡng dự đoán. Không gọi đây là RITA hay công thức của bài báo.

## Công việc của B

- HMM: quan sát, trạng thái ẩn, chuyển trạng thái, phương pháp học và chấm điểm.
- CT-HMM: xác minh thành phần thời gian liên tục và khả năng sử dụng mã phù hợp; ghi rõ phần tự thực hiện.
- TSD: chốt trục thời gian, chu kỳ, cách lấy phần dư và xử lý chuỗi ngắn/phần dư hằng.
- Kết hợp: đối chiếu đúng quy tắc ở từng đặc trưng và cách tổng hợp của bài báo.
- Ghi trường hợp không hội tụ, số trạng thái, tham số, hạt giống và cách chọn trên tập phát triển.

## Bảng đối chiếu cần hoàn thành

> Toàn văn bài báo (Mahboubi và cộng sự, JNCA 2025, DOI 10.1016/j.jnca.2025.104127) **chưa truy cập được** khi sửa PR #8 (ScienceDirect trả 403, không tìm thấy bản preprint). Cột "Mô tả bài báo" vì vậy vẫn chưa kiểm tra; mọi công thức dưới đây là lựa chọn của nhóm và phải đối chiếu lại khi có bản PDF.

| Thành phần | Mô tả bài báo đã kiểm tra | Triển khai của nhóm | Khác biệt và ảnh hưởng |
| --- | --- | --- | --- |
| Gom nhóm | Chưa điền | CSV mẫu theo bốn trường | Chưa đối chiếu dữ liệu thật |
| HMM | Chưa kiểm tra | `src/models/hmm.py`, hmmlearn GaussianHMM, chọn số trạng thái bằng BIC | Điểm = n_b/d × 1/(1+CV_b), xem bên dưới |
| CT-HMM | Chưa kiểm tra | `src/models/ct_hmm.py`, tự cài EM, P(Δt)=expm(QΔt) | Cập nhật Q là xấp xỉ bậc một, xem bên dưới |
| TSD | Chưa kiểm tra | `src/models/tsd.py`, `seasonal_decompose` cộng tính | Điểm có thêm hệ số độ lớn phần dư |
| Điểm kết hợp | Chưa kiểm tra | `src/models/ensemble.py`: max theo đặc trưng, rồi trung bình | Mặc định `fallback`, bỏ thành phần thiếu |

Mã HMM thường không tự trở thành CT-HMM chỉ bằng việc sử dụng khoảng thời gian làm quan sát. Mọi lựa chọn thay thế phải được nêu rõ trong báo cáo và chốt phạm vi với giảng viên khi cần.

## Điểm của HMM và CT-HMM

Cả hai mô hình dùng chung `src/models/state_scoring.py`:

```
S = (n_b / d) · 1 / (1 + CV_b),   CV_b = σ_b / |μ_b|
```

- `n_b`: số quan sát được Viterbi gán vào trạng thái chiếm đa số `b`; `d`: số quan sát.
- `σ_b, μ_b`: tham số phát xạ Gaussian của trạng thái `b`.
- `S ∈ [0, 1]`, điểm cao nghĩa là giống beaconing.

Lý do thay đổi so với bản đầu của PR #8 (chỉ dùng `n_b / d` với 2 trạng thái cố định):

1. `n_b / d` đo độ *lệch* giữa các trạng thái chứ không đo độ đều. Khoảng thời gian ngẫu nhiên (phân phối mũ) được khớp thành một trạng thái "khoảng ngắn" lớn và một trạng thái đuôi nhỏ, nên `n_b / d` cao. Beacon có jitter bị ép chia đôi, nên `n_b / d` chỉ khoảng 0,5. Kết quả là chiều điểm bị ngược: random_arrivals 0,75 > jitter 0,68 (HMM, evaluation-v1/test).
2. Log-likelihood chỉ dùng để chọn lần khởi tạo tốt nhất (lấy giá trị lớn nhất, dấu đúng). Lỗi không nằm ở dấu mà ở định nghĩa điểm bỏ qua độ phân tán của trạng thái.
3. Số trạng thái được chọn trong `1..n_states` bằng BIC (`state_selection: "bic"`; `"fixed"` giữ hành vi cũ). Số tham số được tính là `(k−1) + k(k−1) + 2k`.

### Phương sai tối thiểu

Phương sai phát xạ bị chặn dưới bởi `(variance_floor_ratio · max(|mean|, std))²`, mặc định `variance_floor_ratio = 1e-3`, cả khi khởi tạo lẫn khi cập nhật M-step (HMM dùng `min_covar` của hmmlearn). Chuỗi có phương sai không vượt ngưỡng này được khớp đúng bằng một trạng thái Gaussian. Khi đó `CV_b ≈ 1e-3` và điểm khoảng 0,999. Bản cũ bỏ qua các chuỗi này với lý do `zero_variance`, làm mất 20/20 nhóm regular, dù đây là dấu hiệu beaconing mạnh nhất.

## CT-HMM: phép xấp xỉ khi cập nhật Q

Hàm `update_generator` trong `src/models/ct_hmm.py` tính, với i ≠ j:

```
q_ij = (N_ij + ε) / (T_i + ε)
N_ij = Σ_k ξ_k(i, j)            số lần chuyển i→j kỳ vọng giữa quan sát k và k+1
T_i  = Σ_k γ_k(i) · Δt_k        thời gian lưu kỳ vọng ở i
q_ii = −Σ_{j≠i} q_ij
```

Đây là ước lượng hợp lý cực đại dạng đóng của một CTMC *quan sát đầy đủ* ("số lần chuyển / thời gian lưu"), đặt thẳng vào thống kê của HMM rời rạc. EM chính xác cho CT-HMM (Metzner và cộng sự 2007; Liu và cộng sự 2015, NIPS "Efficient Learning of Continuous-Time Hidden Markov Models") tính `E[N_ij | trạng thái ở hai đầu khoảng]` và `E[T_i | trạng thái ở hai đầu khoảng]` bằng tích phân `∫₀^Δt expm(Qs) e_i e_jᵀ expm(Q(Δt−s)) ds`, đánh giá qua ma trận khối Van Loan `expm([[Q, E_ij], [0, Q]] Δt)`. So với cách đó, mã của nhóm khác ở hai điểm:

1. **Tối đa một bước nhảy trong mỗi khoảng.** `ξ_k(i, j)` là xác suất ở i tại k và ở j tại k+1. Mã dùng nó như số lần nhảy i→j kỳ vọng, nên bỏ qua nhiều bước nhảy trong cùng một Δt. Chuỗi i→j→i trong một khoảng không được đếm.
2. **Toàn bộ Δt_k được tính cho trạng thái đầu khoảng**, có trọng số `γ_k(i)`, thay vì thời gian lưu kỳ vọng có điều kiện theo cả hai đầu.

Ảnh hưởng: phép xấp xỉ gần đúng khi `q_ij · Δt ≪ 1`. Khi chuyển trạng thái có khả năng xảy ra trong một khoảng, tốc độ chuyển bị ước lượng thấp và thời gian lưu bị phân bổ sai. `ε = 1e-8` tránh chia cho 0. Hàng của trạng thái gần như không có thời gian lưu được đặt bằng 0 (hấp thụ) trong vòng lặp đó. Vì điểm chỉ dùng chuỗi trạng thái Viterbi và tham số phát xạ, sai lệch của Q ảnh hưởng tới điểm qua `P(Δt)` khi giải mã, không ảnh hưởng trực tiếp tới công thức điểm. **Không được ghi là đã tái lập đúng EM của CT-HMM.**

Tối ưu tốc độ (không làm đổi kết quả):

- `transition_matrices(Q, Δt)` gọi `expm` theo lô một lần cho các Δt *khác nhau* trong mỗi vòng EM; Δt = 0 cho ma trận đơn vị. Không thể cache giữa các vòng vì Q thay đổi.
- Forward-backward dùng xác suất có chuẩn hóa từng bước (Rabiner) thay cho `logsumexp` ở từng bước, và tính `ξ` bằng một biểu thức vector. Khi bị tràn dưới, mã quay về bản log-space. Test so sánh hai bản đến sai số 1e-9.
- EM dừng ở `n_iter` (mặc định 50) hoặc khi `|ΔLL| ≤ tolerance · max(1, |LL|)`. Số vòng thực tế được ghi vào `metadata.em_iterations`.

## TSD

Phân rã cộng tính `seasonal_decompose` với chu kỳ `period` (chế độ `event`) hoặc `clock_period_seconds / bin_size_seconds` (chế độ `clock`). Gọi phần dư là R và mức là `level = mean(|x|)`:

```
score = (1 − n_a / d) · 1 / (1 + std(R) / level)
```

`n_a` là số phần dư có z-score vững (median, 1,4826·MAD; dùng độ lệch chuẩn khi MAD = 0) vượt `z_threshold`. Bản cũ chỉ dùng `1 − n_a/d` với z chuẩn hóa bằng độ lệch chuẩn của *chính* phần dư. Cách này không phụ thuộc thang đo: với nhiễu gần đối xứng thì `n_a/d ≈ 0,3%`, nên mọi nhóm đều được khoảng 1,0. Hệ số `1/(1 + std(R)/level)` đưa độ lớn phần dư so với mức của chuỗi vào điểm.

## Kết hợp

Theo từng đặc trưng, lấy max của các điểm thành phần có mặt (HMM hoặc CT-HMM, và TSD). Theo nhóm, lấy trung bình của các đặc trưng có ít nhất một điểm. Mặc định là `partial_policy: "fallback"`: thành phần thiếu thì bỏ qua thành phần đó, và nhóm chỉ bị bỏ khi không thành phần nào chấm được đặc trưng nào. `"strict"` vẫn có nhưng phải bật rõ. Với `strict` làm mặc định, evaluation-v1 mất cả 80/80 nhóm: `bytes_sent` là hằng (500) ở mọi nhóm, nên nhánh trạng thái bỏ đặc trưng này và `strict` bỏ luôn cả nhóm.

## Đánh giá trên evaluation-v1

Chạy `python -m src.evaluate_models`. Kết quả ghi vào `outputs/model-evaluation-v1/`. Ngưỡng được chọn trên dev rồi áp nguyên cho test. Lưu ý: `bytes_sent` là hằng nên điểm theo đặc trưng này ≈ 1 cho mọi nhóm. Điểm nhóm vì vậy bị nén về phía trên (thứ tự giữ nguyên), và chỉ `time_deltas` mang thông tin phân biệt.
