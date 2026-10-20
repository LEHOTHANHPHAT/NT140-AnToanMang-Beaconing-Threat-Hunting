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

| Thành phần | Mô tả bài báo đã kiểm tra | Triển khai của nhóm | Khác biệt và ảnh hưởng |
| --- | --- | --- | --- |
| Gom nhóm | Chưa điền | CSV mẫu theo bốn trường | Chưa đối chiếu dữ liệu thật |
| CT-HMM | Chưa điền | Chưa triển khai | Không được ghi đã tái lập |
| TSD | Chưa điền | Chưa triển khai | Chưa kết luận |
| Điểm kết hợp | Chưa điền | Chưa triển khai | Chưa kết luận |

Mã HMM thường không tự trở thành CT-HMM chỉ bằng việc sử dụng khoảng thời gian làm quan sát. Mọi lựa chọn thay thế phải được nêu rõ trong báo cáo và chốt phạm vi với giảng viên khi cần.
