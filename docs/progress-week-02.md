# Tiến độ tuần 2 — Thành Phát

Ngày cập nhật: 2026-10-27
Trạng thái: Đã chuẩn bị dữ liệu TCP cho phát triển mô hình; tuần 2 chưa hoàn tất.

## Công việc đã hoàn thành

- Tải CTU-13 Scenario 1: capture20110810.binetflow.
- Thêm bộ chuyển đổi src/data/prepare_ctu13.py.
- Thêm kiểm thử và quy ước docs/ctu13-contract.md.
- Chạy thành công 29 kiểm thử.
- Kiểm tra mã nhóm, ghép nhãn, thứ tự thời gian và độ dài chuỗi: đạt.

## Kết quả xử lý

| Nội dung | Kết quả |
| --- | ---: |
| Tổng bản ghi gốc | 2.824.636 |
| Bản ghi TCP gốc | 507.557 |
| TCP bị loại vì thiếu giá trị bắt buộc, khớp số dòng thiếu Dport | 675 |
| TCP hợp lệ | 506.882 |
| Nhóm trước lọc độ dài | 131.479 |
| Nhóm dưới 5 bản ghi | 120.232 |
| Nhóm được xuất | 11.247 |
| Bản ghi được xuất | 353.821 |
| Khoảng thời gian bằng 0 trong phần xuất | 0 |

Nhóm được xuất: Background 10.665; Normal 291; Botnet 291.
Không có nhóm mixed/unknown trong phần được xuất.

Độ dài nhóm: nhỏ nhất 5, trung vị 9, lớn nhất 7.035 bản ghi.
Có 7 nhóm chứa ít nhất một nhãn có token CC+số.

## Ảnh hưởng của ngưỡng độ dài

| Ngưỡng bản ghi | Tổng nhóm còn lại | Nhóm có nhãn CC còn lại |
| --- | ---: | ---: |
| 5 | 11.247 | 7 |
| 10 | 5.585 | 4 |
| 20 | 3.009 | 3 |
| 30 | 2.042 | 2 |
| 50 | 1.213 | 2 |
| 100 | 556 | 1 |

Giữ ngưỡng 5 cho bản thử hiện tại; chưa chốt ngưỡng cho mô hình.

## Các trường hợp cần khảo sát tiếp

- Đích 31.192.109.167:80: 53 bản ghi, đều có nhãn CC53.
  Nhiều khoảng cách đầu khoảng 120–123 giây; cần xem toàn chuỗi.
- Đích 173.192.170.88:80: 266 bản ghi, gồm 221 nhãn CC16
  và 45 nhãn TCP-Attempt; không coi toàn bộ bản ghi là C2 đã xác minh.
- Đích 213.246.53.125:5296: 9 bản ghi, có thay đổi nhịp
  và lượng byte; cần kiểm tra ảnh hưởng cách xuất flow.
- Các nhóm CC còn lại cần được vẽ biểu đồ và phân tích thêm.

## Bàn giao cho Huy Phát

Đọc START_HERE_WEEK2.md và docs/ctu13-contract.md.

Dữ liệu được tạo tại:
data/processed/ctu13/scenario-01-tcp/

- flows.json: đầu vào phát triển mô hình, schema 1.1.
- summary.json: nguồn, SHA-256, tham số và chất lượng dữ liệu.
- labels.json: dùng riêng cho phân tích/đánh giá, không làm đặc trưng mô hình.

Huy Phát có thể tái tạo dữ liệu theo lệnh trong START_HERE_WEEK2.md.
Code và tài liệu nằm trên Git; dữ liệu thật được tải và tạo riêng.

Yêu cầu phần mô hình:
- Đọc schema 1.1, giữ đúng flow_id.
- relative_times_seconds và bytes_sent có N phần tử.
- time_deltas có N-1 phần tử.
- Kiểm tra bytes_semantics và timestamp_basis.
- Giữ ranh giới giữa các nhóm khi học từ nhiều chuỗi.
- Trả status/reason cho trường hợp không xử lý được; không tạo điểm giả.
- Kiểm tra nhu cầu số quan sát tối thiểu và tính khả thi CT-HMM.

## Giới hạn hiện tại

- Chỉ xử lý TCP, chưa bao phủ UDP/DNS.
- Ngưỡng 5 phục vụ thử đường chạy, chưa bảo đảm đủ dữ liệu cho mô hình.
- Nhãn Botnet hoặc CC chưa phải ground truth beaconing.
- Background không mặc định là lưu lượng lành tính.
- Chưa chia tập phát triển/kiểm tra độc lập.
- Scenario 1 đang dùng để phát triển, chưa dùng để báo cáo kết quả kiểm tra cuối.

