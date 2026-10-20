# Beaconing Threat Hunting

Đồ án nhóm 2 người về phát hiện dấu hiệu beaconing từ log mạng, tham chiếu bài báo **Lurking in the shadows: Unsupervised decoding of beaconing communication for enhanced cyber threat hunting**.

Mục tiêu: chuẩn bị dữ liệu, phân tích chuỗi giao tiếp, xếp hạng nhóm nghi vấn và so sánh các phương pháp. Điểm số giúp chọn nhóm cần điều tra; không tự chứng minh có mã độc.

## 1. Trạng thái hiện tại

Đây là bộ khung khởi đầu, phiên bản `0.1.0`.

| Thành phần | Trạng thái |
| --- | --- |
| Đọc CSV mẫu, kiểm tra dữ liệu, gom nhóm, tính khoảng thời gian | Chạy được |
| Xuất JSON có mã nhóm và thống kê chất lượng | Chạy được |
| Baseline đo độ đều theo thời gian | Chạy được; là baseline đơn giản của nhóm |
| Kiểm thử và workflow GitHub Actions | Đã chuẩn bị; Actions chạy sau khi push lên GitHub |
| Bộ chuyển CTU-13, HMM, CT-HMM, TSD, kết hợp, chỉ số đánh giá | Có file và giao diện; chưa triển khai |

Các hàm chưa triển khai phát sinh `NotImplementedError`, không trả điểm giả. Repo này **chưa phải mã nguồn chính thức của tác giả và chưa tái lập đầy đủ NetSpectra Sentinel**. HMM thường và CT-HMM phải được phân biệt trong báo cáo.

## 2. Phân công hai người

| Phần việc | Người A — bạn | Người B — thành viên còn lại |
| --- | --- | --- |
| Dữ liệu và phương pháp | `src/data/`, `src/baselines/` | `src/models/` |
| Chạy và đánh giá | `src/evaluation/`, dữ liệu mẫu và lab | `src/runner.py`, `configs/`, `requirements.txt` |
| Tài liệu | Dữ liệu, thực nghiệm, kết quả, README | Phương pháp, sơ đồ, hạn chế mô hình |
| Kiểm tra | Test dữ liệu và đánh giá | Test mô hình |

Quy ước dữ liệu phải được hai người thống nhất trước khi sửa. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [phân công](docs/team.md) và [kế hoạch 8 tuần](docs/plan-8-weeks.md).

## 3. Các thư mục chính

| Đường dẫn | Dùng để làm gì |
| --- | --- |
| `configs/` | Cấu hình đường dẫn và tham số |
| `data/sample/` | Dữ liệu nhỏ được commit để kiểm tra code |
| `data/raw/` | Dữ liệu gốc tải về; không commit dữ liệu lớn |
| `data/interim/` | Dữ liệu trung gian |
| `data/processed/` | JSON đã tiền xử lý |
| `src/data/` | Bộ đọc và chuyển dữ liệu |
| `src/baselines/` | Phương pháp thống kê làm mốc so sánh |
| `src/models/` | HMM, CT-HMM, TSD và kết hợp |
| `src/evaluation/` | Ghép nhãn và tính chỉ số |
| `tests/` | Kiểm tra tính đúng của code |
| `experiments/` | Kế hoạch, mẫu nhật ký thực nghiệm |
| `outputs/` | Điểm số, biểu đồ, chỉ số, log, mô hình đã lưu |
| `lab/` | Tài liệu và vị trí code tạo giao tiếp trong lab |
| `docs/` | Quy ước dữ liệu, phương pháp, phân công, nguồn tham khảo |
| `reports/` | Báo cáo, slide và khai báo sử dụng AI |
| `.github/` | Workflow kiểm tra, mẫu task và pull request |

Thư mục chưa có dữ liệu chứa README để Git vẫn lưu được cấu trúc. Các file sinh tự động đã được loại khỏi Git bằng `.gitignore`.

## 4. Cài đặt

Cần **Python 3.10 trở lên** và Git. Chạy lệnh trong thư mục có README này. Bộ khung hiện chỉ dùng thư viện chuẩn, chưa cần Docker hoặc cài thư viện mô hình.

### Windows PowerShell

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.runner demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Dùng trực tiếp Python trong `.venv` nên không cần thay đổi PowerShell Execution Policy.

### Ubuntu hoặc WSL

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.runner demo
.venv/bin/python -m unittest discover -s tests -v
```

Nếu Ubuntu thiếu mô-đun `venv`, cài gói `python3-venv` bằng trình quản lý gói của hệ điều hành, rồi tạo lại môi trường.

## 5. Chạy thử và hiểu kết quả

Các ví dụ dưới đây dùng `python`; trên Windows có thể thay bằng `.\.venv\Scripts\python.exe`, trên Ubuntu thay bằng `.venv/bin/python`.

```bash
# Chạy tiền xử lý và baseline
python -m src.runner demo

# Hoặc chạy từng phần
python -m src.runner prepare
python -m src.runner baseline

# Dùng cấu hình riêng
python -m src.runner demo --config configs/default.json
```

CSV mẫu có 8 sự kiện thuộc 2 nhóm. Kết quả mong đợi:

```text
Prepared 8 events / 2 groups.
Baseline: 1 scored / 1 skipped.
```

Chương trình cũng in đường dẫn các file đã tạo:

- `data/processed/flows.json`: chuỗi thời gian và byte của từng nhóm.
- `outputs/scores/baseline.json`: điểm và trạng thái xử lý của baseline.

| Nhóm | Khoảng thời gian giây | Kết quả mặc định |
| --- | --- | --- |
| `192.168.1.10` đến `192.168.1.20:80/tcp` | `[60, 62, 59, 59]` | Đủ 5 sự kiện để tính điểm |
| `192.168.1.11` đến `192.168.1.30:443/tcp` | `[15, 155]` | Bỏ qua vì chỉ có 3 sự kiện |

Baseline dùng `score = 1 / (1 + CV)`, trong đó CV là độ lệch chuẩn tổng thể chia trung bình của khoảng thời gian. Điểm cao biểu thị khoảng thời gian đều hơn. Đây **không phải RITA**, không phải mô hình bài báo, và không phải xác suất có mã độc. Mốc `min_events = 5` chỉ để chạy ví dụ; cần chọn lại trên tập phát triển khi làm thực nghiệm.

`labels.example.csv` chỉ mô tả mẫu thời gian giả lập; không có nhãn mã độc để tính Precision/Recall của phát hiện tấn công. Dữ liệu mẫu không được dùng làm bằng chứng hiệu quả trên dữ liệu thật.

## 6. Chuẩn bị dữ liệu thật

1. Đọc [quy ước dữ liệu](docs/data-contract.md) và [kế hoạch đánh giá](docs/experiment-plan.md).
2. Tải từng kịch bản từ [nguồn CTU-13](https://www.stratosphereips.org/datasets-ctu13), lưu vào `data/raw/`.
3. Ghi nguồn, kịch bản, phiên bản và ý nghĩa các trường; giữ nguyên dữ liệu gốc.
4. Triển khai `src/data/ctu13.py`; không đưa trực tiếp định dạng CTU-13 vào bộ đọc CSV mẫu.
5. Tách nhãn đánh giá khỏi đầu vào mô hình; chốt cách xử lý Background và nhãn trộn.

Không đổi tổng byte hai chiều thành byte gửi nếu dữ liệu nguồn không có ý nghĩa đó. Không coi mọi lưu lượng botnet là beaconing.

## 7. Tạo repository GitHub và push lần đầu

Phần này do **một người thực hiện một lần**. Bộ ZIP không chứa `.git`; tạo lịch sử Git trên máy của bạn bằng các lệnh sau.

1. Đăng nhập GitHub, chọn **New repository**.
2. Đặt tên `beaconing-threat-hunting`; chọn quyền riêng tư theo yêu cầu môn học.
3. **Không chọn tạo README, .gitignore hoặc license trên GitHub**, vì bộ mã đã có các file khởi đầu.
4. Trong thư mục đã giải nén, thay `YOUR_USERNAME` bằng tài khoản thực tế rồi chạy:

```bash
git init -b main
git add .
git status
git commit -m "chore: initialize beaconing project scaffold"
git remote add origin https://github.com/YOUR_USERNAME/beaconing-threat-hunting.git
git push -u origin main
```

Nếu Git yêu cầu tên/email tác giả, cấu hình bằng danh tính của bạn trước khi commit. Đăng nhập theo hướng dẫn Git/GitHub trên máy; không ghi token vào URL hoặc file dự án. Nếu thư mục đã có remote hoặc lịch sử riêng, kiểm tra `git remote -v` và lịch sử trước, không dùng force push.

Sau khi push, mời thành viên còn lại trong phần quản lý collaborators của repository. Khi đủ điều kiện trên tài khoản, cấu hình quy tắc cho `main`: yêu cầu pull request, một người review và CI thành công. `CODEOWNERS` chỉ là mẫu comment đến khi điền đúng tài khoản; chưa tự kích hoạt bảo vệ nhánh.

Người thứ hai clone repository từ GitHub; **không giải nén một bản khác rồi tạo lịch sử Git độc lập**.

## 8. Làm việc hằng ngày

```bash
git switch main
git pull --ff-only
git switch -c feature/data-pipeline
# Sửa file và chạy kiểm tra
python -m unittest discover -s tests -v
git add src/data tests/data docs/data-contract.md
git commit -m "feat(data): describe the concrete change"
git push -u origin feature/data-pipeline
```

Người B dùng tên nhánh như `feature/hmm-model`. Mở pull request và nhờ người còn lại review. Không tự ý sửa file người kia đang làm. Nếu `pull --ff-only` báo lỗi, dừng để kiểm tra sự phân nhánh; không xóa lịch sử để vượt lỗi.

## 9. Mốc 8 tuần

| Tuần | Người A | Người B | Bàn giao chung |
| --- | --- | --- | --- |
| 1 | CSV, tiền xử lý, quy ước dữ liệu | Đọc phương pháp, giao diện mô hình | Ghép đầu vào và đầu ra mẫu |
| 2 | Dữ liệu thật, nhãn và chia tập | Kiểm tra khả thi CT-HMM | Chốt schema và phạm vi |
| 3 | Baseline và dữ liệu mô phỏng | HMM cơ sở | So sánh điểm trên cùng nhóm |
| 4 | Bộ đánh giá và ngưỡng phát triển | Nhánh trạng thái ẩn đã chốt | Khóa quy trình kiểm tra |
| 5 | Lab và tích hợp dữ liệu | TSD và kết hợp | Bản chạy từ đầu đến cuối |
| 6 | Thí nghiệm, chỉ số, lỗi tiêu biểu | So sánh mô-đun, độ ổn định | Bảng kết quả có nguồn chạy |
| 7 | Báo cáo dữ liệu và kết quả | Báo cáo phương pháp | Bản thảo và slide |
| 8 | Chạy lại độc lập, demo | Sửa lỗi, đóng gói mô hình | Bản cuối và bảo vệ |

Chi tiết: [docs/plan-8-weeks.md](docs/plan-8-weeks.md). Mỗi người dự kiến 12 giờ/tuần, gồm 10 giờ riêng và 2 giờ phối hợp.

## 10. Tài liệu và trích dẫn

- [Quy trình đóng góp](CONTRIBUTING.md)
- [Quy ước đầu vào và đầu ra](docs/data-contract.md)
- [Ghi chú phương pháp](docs/methodology.md)
- [Kế hoạch thực nghiệm](docs/experiment-plan.md)
- [Mẫu báo cáo](reports/report.md)
- [Khai báo hỗ trợ AI](reports/ai-disclosure.md)
- [Nguồn tham khảo](docs/references.md)

Chưa chọn giấy phép phân phối mã nguồn. Hai thành viên cần thống nhất giấy phép và yêu cầu môn học trước khi phát hành cho người khác sử dụng; giấy phép dữ liệu và mã bên thứ ba được giữ riêng theo nguồn.
