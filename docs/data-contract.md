# Quy ước dữ liệu phiên bản 1.0

## 1. Đơn vị phân tích

Một dòng CSV mẫu là một lần giao tiếp được ghi nhận. Bộ đọc mẫu gom các dòng theo `(src_ip, dst_ip, dst_port, protocol)` trong cùng dataset. Nhóm này không đồng nghĩa một kết nối TCP duy nhất hay một packet.

`flow_id` hiện là `dataset_id|src_ip|dst_ip|dst_port|protocol`. Khi thêm kịch bản hoặc cửa sổ quan sát, dataset_id phải phân biệt chúng; không gộp nhiều lần thu dưới cùng dataset_id. Nếu cần cấu trúc mã khác, cập nhật schema và bên ghép nhãn trong cùng pull request.

## 2. CSV mẫu

| Trường | Kiểu | Quy ước |
| --- | --- | --- |
| timestamp | Chuỗi datetime ISO | Có thể kèm offset; chuẩn hóa UTC. Mẫu không có offset được giả định UTC và đếm trong quality. |
| src_ip, dst_ip | Địa chỉ IPv4 hoặc IPv6 | Kiểm tra bằng ipaddress |
| dst_port | Số nguyên | Từ 0 đến 65535; ý nghĩa cổng 0 phải theo bộ chuyển nguồn |
| protocol | Chuỗi không rỗng | Chuyển về chữ thường |
| bytes_sent | Số nguyên không âm | Byte gửi từ phía khởi tạo cho mỗi lần giao tiếp, không phải tổng hai chiều |

Sai cột hoặc giá trị: dừng với số dòng lỗi; không âm thầm bỏ dòng. Trùng sự kiện: giữ và thống kê. Timestamp bằng nhau: giữ thứ tự tương đối trong CSV, khoảng thời gian có thể bằng 0. Giá trị byte và timestamp được sắp xếp cùng sự kiện.

## 3. JSON tiền xử lý

Đối tượng gốc gồm `schema_version`, `source`, `quality`, `flows`.

Mỗi phần tử flows có:

- `flow_id`, `src_ip`, `dst_ip`, `dst_port`, `protocol`.
- `event_count`: số sự kiện.
- `timestamps`: thời điểm UTC, sắp xếp tăng dần.
- `time_deltas`: khoảng thời gian giữa các sự kiện liên tiếp, đơn vị giây.
- `bytes_sent`: lượng byte cùng thứ tự với timestamps.
- `bytes_semantics`: hiện là `originator_sent_bytes`.

N sự kiện tạo N trừ 1 khoảng thời gian. Hai chuỗi khoảng thời gian và byte có thể được chấm riêng; không ghép cột tùy ý khi độ dài khác nhau. Không đưa nhãn, địa chỉ IP hay mã nhóm vào đặc trưng chỉ vì chúng nằm trong JSON; mô hình phải khai báo rõ trường đặc trưng sử dụng.

## 4. JSON điểm số

Đối tượng gốc gồm `schema_version` và `scores`. Mỗi dòng điểm có:

| Trường | Ý nghĩa |
| --- | --- |
| flow_id | Mã nhóm, dùng ghép với nhãn |
| method | Tên phương pháp thực sự đã chạy |
| event_count | Số sự kiện đầu vào |
| score | Điểm xếp hạng; null nếu không tính được |
| status | ok, skipped hoặc error; baseline hiện dùng ok/skipped |
| reason | Chuỗi giải thích; rỗng khi thành công |

Không gán score bằng 0 để che lỗi hoặc trường hợp thiếu dữ liệu. Không diễn giải điểm là xác suất tấn công nếu chưa hiệu chuẩn.

## 5. Dữ liệu thật và nhãn

CTU-13 cần bộ chuyển riêng. Chưa tự động ánh xạ trường tổng byte sang bytes_sent. Nếu chỉ có tổng byte, đề xuất trường/feature có ý nghĩa tổng byte và cập nhật schema trước khi dùng.

Nhãn đánh giá nằm riêng và ghép bằng flow_id. Chốt rõ nhãn botnet, C2, beaconing, Background và nhóm có nhãn trộn trong `docs/experiment-plan.md`. Không mặc định Background là normal hoặc mọi botnet là beaconing.

`data/sample/labels.example.csv` chỉ mô tả chuỗi giả lập. Không dùng hai nhãn đó làm nhãn mã độc thật.
