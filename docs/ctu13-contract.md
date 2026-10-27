# CTU-13: quy ước bàn giao tuần 2 (schema 1.1)

Tài liệu này bổ sung `docs/data-contract.md` cho CTU-13. Không thay đổi dữ liệu mẫu schema 1.0.

## Phạm vi bản đầu

- Scenario 1, toàn bộ TCP hợp lệ, gom theo `(SrcAddr, DstAddr, Dport, Proto)`.
- Xuất nhóm có ít nhất 5 bản ghi. Đây là ngưỡng thử đường chạy, không phải điều kiện khoa học đã chứng minh đủ cho HMM/CT-HMM.
- Không chọn nhóm theo nhãn, điểm đều đặn hoặc IP máy nhiễm. Các bản ghi ngắn bị loại chỉ vì điều kiện số quan sát và được thống kê.
- Toàn bộ bản ghi, kể cả TCP không thiết lập thành công, vẫn nằm trong phạm vi nếu hợp lệ. Không gọi bộ này là tập C2 thuần.
- Bản TCP ban đầu chưa bao phủ UDP/DNS. Có thể chạy `--protocols tcp udp` trong thư mục và dataset_id khác; ghi nhận phạm vi rõ ràng.
- Chưa có train/dev/test. Huy Phát dùng bản này để phát triển mô hình; không dùng lại nó như tập kiểm tra độc lập sau khi chỉnh mô hình.

## Các thay đổi cần Huy Phát hỗ trợ

`flows.json` có `schema_version: "1.1"`, `source`, `run_id`, `flows`, `quality`.
Các tên `flow_id`, `event_count`, `time_deltas`, `bytes_sent` giữ nguyên để phối hợp code.

| Trường | Ý nghĩa |
| --- | --- |
| flow_id | dataset_id\|src_ip\|dst_ip\|dst_port\|protocol |
| timestamps | Chuỗi ISO theo đồng hồ nguồn, **không có Z hoặc offset**, chưa xác nhận múi giờ |
| timestamp_basis | source_clock_timezone_unverified |
| relative_times_seconds | N thời điểm, tính bằng giây từ bản ghi đầu của nhóm; bắt đầu 0 |
| time_deltas | N-1 khoảng cách giữa các StartTime liên tiếp, giây |
| bytes_sent | N giá trị SrcBytes theo đúng thứ tự bản ghi; không dùng TotBytes |
| bytes_semantics | argus_src_bytes; không khẳng định phía nguồn luôn là client/initiator |

Không dùng `src.runner prepare/demo` để đọc `.binetflow`: bộ đọc đó chỉ dành cho CSV mẫu.
`src.runner baseline` cũ kiểm tra schema 1.0 nên chưa tự nhận schema 1.1. Không sửa nhãn phiên bản thành 1.0 để vượt kiểm tra.
Huy Phát cần kiểm tra các quy ước trên khi thêm loader 1.1. Nếu chỉ muốn thử baseline, có thể gọi hàm `score_flows(payload["flows"])` trực tiếp, không qua runner cũ.

Nếu mô hình quan sát byte tại mỗi thời điểm, dùng cặp `relative_times_seconds[i]`, `bytes_sent[i]` (N cặp).
Không tự ghép `time_deltas` (N-1 phần tử) với toàn bộ `bytes_sent` (N phần tử).
Nếu thuật toán cần quan sát theo khoảng cách, phải thống nhất riêng căn chỉnh và ghi trong phần phương pháp.

## Hướng và đơn vị quan sát

Một dòng là bản ghi luồng hai chiều của Argus, không đồng nghĩa packet, HTTP request hay beacon.
Giữ nguyên SrcAddr/DstAddr, không suy đoán đảo chiều từ Dir (trong dữ liệu có `<?>`).
Vì vậy, nhóm server -> client có thể bị chia theo cổng đích tạm thời; đây là giới hạn cần phân tích, không phải lỗi code.
Không gộp hai chiều, không sử dụng Sport trong khóa. Dir được thống kê riêng trong labels.json để rà soát.
StartTime có thể chịu ảnh hưởng cách xuất/timeout của flow collector. Nhịp của bản ghi không tự chứng minh nhịp beacon thực tế.

Timestamp được sort cùng toàn bộ sự kiện. Timestamp bằng nhau giữ thứ tự tương đối CSV.
Giữ bản ghi trùng; không âm thầm xóa các lần quan sát. Có thể có khoảng cách 0.
Nhóm toàn khoảng cách 0 cần mô hình báo skipped/unsupported hoặc áp dụng cách xử lý được giải thích rõ, không tự thêm epsilon tùy ý.
Không khẳng định timezone, không gắn Z giả. Khoảng cách trong cùng kịch bản dùng đồng hồ nguồn; khi cần ghép nguồn hoặc có biến đổi đồng hồ phải xác minh lại.

## Nhãn và đánh giá độc lập

`labels.json` ghép qua flow_id, tách khỏi `flows.json`.
`category` gồm botnet, normal, background, unknown, mixed. Nhận dạng loại bằng tiền tố nhãn gốc (có hoặc không có From-/To-).
`mixed` nghĩa nhiều loại khác nhau trong cùng nhóm; nhiều nhãn chi tiết cùng loại vẫn có thể có category duy nhất.
Giữ `raw_label_counts`, `category_counts`, `cc_annotated_rows`, `direction_counts`.
`cc_annotated_rows` chỉ đếm nhãn chứa token CC + số (ví dụ CC16). Đây là dấu hiệu để người làm đánh giá rà soát, không phải định nghĩa đầy đủ mọi C2, càng không phải nhãn beaconing.
Mọi nhóm có `beaconing_ground_truth: "not_established"`.

Không đưa labels, category, IP, flow_id hoặc direction_counts trong file audit vào đặc trưng mô hình chỉ vì chúng có sẵn.
Background chưa được xác minh normal. Botnet không đồng nghĩa tất cả các bản ghi là C2 hoặc beaconing.
Không tự đưa nhóm mixed/unknown vào confusion matrix nhị phân. Chốt chính sách trước thực nghiệm.

## Chất lượng và tái lập

`summary.json` ghi SHA-256, dung lượng, URL nếu truyền qua CLI, phạm vi giao thức, min_events, lỗi mẫu có số dòng, phân bố giao thức và nhãn gốc.
Đếm Dport trống cho **mọi** giao thức trước khi lọc. Bản TCP không hợp lệ được đếm riêng, không tự điền cổng/byte 0.
Một dòng chỉ thuộc một nhánh chất lượng:

`total_rows = protocol_filtered_rows + invalid_selected_rows + accepted_rows`

`accepted_rows = short_group_rows + exported_rows`

`groups_before_min_events = short_groups + exported_groups`

File header thiếu/trùng cột và file không có bản ghi được chọn hợp lệ: dừng. Nếu mọi nhóm đều quá ngắn thì xuất tập rỗng và ghi rõ thống kê.
SHA-256 và các tham số cho phép đối chiếu cùng đầu vào; run_id khác nhau giữa hai lần chạy là bình thường. So sánh nội dung flows khi kiểm tra tái lập.
Ba file cùng một lần chạy có cùng run_id. Nếu lệnh bị ngắt, chạy lại và kiểm tra run_id khớp trước bàn giao.
Trên WSL, SQLite tạm dùng thư mục tạm Linux; dành đủ ổ trống cho staging và output (vài GB cho Scenario 1). Dữ liệu được sort bằng index trên đĩa, RAM chỉ giữ một nhóm khi xuất.

## Việc còn lại tuần 2

1. Rà báo cáo chất lượng và lý do dòng TCP bị loại; xem ví dụ lỗi trước khi sửa quy tắc.
2. Kiểm tra số bản ghi gốc: theo kết quả Thành Phát cung cấp là 2,824,636; TCP 507,557. Không dự đoán số nhóm xuất trước khi chạy thật.
3. Huy Phát xác nhận loader 1.1, đọc JSON và trả kết quả cùng flow_id; chưa triển khai phải báo not_implemented, không gán điểm giả.
4. Chốt yêu cầu số quan sát, cách xử lý chuỗi đồng thời, đặc trưng và tính khả thi CT-HMM.
5. Chọn thêm scenario/capture dành riêng cho phát triển và kiểm tra. Không random-split các dòng trong cùng nhóm rồi gọi là độc lập.
6. Hoàn thiện chính sách nhãn C2/beaconing và nhóm trộn trước khi tính chỉ số phát hiện.

## Nguồn

- https://www.stratosphereips.org/datasets-ctu13/
- https://www.stratosphereips.org/datasets-overview
- https://www.stratosphereips.org/datasets-faq
- https://mcfp.felk.cvut.cz/publicDatasets/CTU-Malware-Capture-Botnet-42/detailed-bidirectional-flow-labels/

Trích dẫn dataset theo bên cung cấp: Garcia, Grill, Stiborek, Zunino (2014), An empirical comparison of botnet detection methods, Computers & Security 45, 100–123, doi:10.1016/j.cose.2014.05.011.
