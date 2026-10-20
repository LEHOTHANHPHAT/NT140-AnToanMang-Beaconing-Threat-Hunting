# Kế hoạch thực nghiệm

Đây là kế hoạch, chưa phải kết quả đo.

## Trước khi chạy kiểm tra

1. Chốt mục tiêu nhãn: beaconing, C2 hay botnet; không dùng lẫn khi kết luận.
2. Liệt kê kịch bản phát triển và kịch bản kiểm tra riêng. Dự kiến bắt đầu một kịch bản phát triển, hai kịch bản kiểm tra nếu tài nguyên cho phép; chốt mã kịch bản ở tuần 2.
3. Quy định xử lý Background, nhóm nhãn trộn, chuỗi ngắn và các nhóm thiếu feature.
4. Chọn tham số/ngưỡng trên tập phát triển, không trên tập kiểm tra.
5. Các phương pháp so trên cùng tập nhóm đủ điều kiện, đồng thời báo số nhóm bị bỏ qua.

## Các phương pháp

Baseline thống kê; HMM cơ sở; nhánh CT-HMM nếu triển khai đúng; TSD; kết hợp đã đối chiếu bài báo. Giữ tên phương pháp riêng trong output.

## Các mẫu mô phỏng

Khoảng cách đều, dao động quanh một giá trị, đổi nhịp, không đều và dịch vụ hợp lệ định kỳ. Ghi cách tạo, độ dài, hạt giống và ý nghĩa nhãn. Mô phỏng mẫu thời gian không phải bằng chứng đã phát hiện mã độc thật.

## Chỉ số dự kiến

Ma trận nhầm lẫn, Precision, Recall, F1, FPR; thêm PR-AUC/ROC-AUC khi có nhãn và điểm phù hợp. Báo thời gian chạy, số nhóm và tỷ lệ bỏ qua. Mẫu số bằng 0 phải xử lý và ghi rõ, không tự biến thành kết quả hoàn hảo.

## Tái hiện

Lưu run ID, commit, nguồn dữ liệu, kịch bản, cấu hình, hạt giống, môi trường và output. Dùng mẫu `experiments/run-template.md`. Với mô hình ngẫu nhiên, dự kiến ít nhất ba hạt giống cố định và báo biến động.

Không đổi tham số theo kết quả test rồi báo lại test đó như đánh giá độc lập. Nếu cần sửa sau khi đã xem test, công bố thay đổi và chuẩn bị tập đánh giá mới.
