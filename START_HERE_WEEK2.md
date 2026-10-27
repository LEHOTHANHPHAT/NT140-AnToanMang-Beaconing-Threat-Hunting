# Tuần 2 — Thành Phát chuẩn bị CTU-13 cho Huy Phát

Gói bổ sung cho repository `beaconing-threat-hunting` đã chạy tuần 1. Không chứa log CTU thật hay mô hình đã huấn luyện.
Đã kiểm thử bằng fixture giả lập; dữ liệu 369 MB nằm trên máy của bạn, cần chạy để biết số nhóm thực tế.

## 1. Chép đúng file

Giải nén ZIP vào thư mục tạm, rồi chép các file theo đường dẫn tương ứng vào repository:

- `src/data/prepare_ctu13.py` — bộ chuyển đổi riêng, không thay prepare.py cũ.
- `tests/test_ctu13_adapter.py` — kiểm thử bộ chuyển đổi.
- `docs/ctu13-contract.md` — quy ước cho hai thành viên.
- `START_HERE_WEEK2.md` — hướng dẫn này.

Không chép nguyên thư mục src đè thay thế src cũ; chỉ thêm file mới. Không cần cài thêm thư viện.

## 2. Kiểm tra tích hợp trên WSL

Đứng tại thư mục gốc repository, `.venv` đã kích hoạt:

```bash
python -m unittest discover -s tests -v
```

Bộ khung gốc có 16 test; gói này thêm 13 test. Nếu bản gốc chưa đổi, tổng mong đợi là 29 test OK.
Kiểm thử dùng dữ liệu giả lập để kiểm tra phép biến đổi, không chứng minh khả năng phát hiện C2.

## 3. Xuất dữ liệu TCP thật

```bash
python -m src.data.prepare_ctu13 \
  --input data/raw/ctu13/scenario-01/capture20110810.binetflow \
  --output-dir data/processed/ctu13/scenario-01-tcp \
  --dataset-id ctu13-scenario01-tcp-bootstrap-v1 \
  --protocols tcp \
  --min-events 5 \
  --source-url "https://mcfp.felk.cvut.cz/publicDatasets/CTU-Malware-Capture-Botnet-42/detailed-bidirectional-flow-labels/capture20110810.binetflow"
```

Lệnh đọc toàn bộ file, đếm cổng trống trước lọc, chọn TCP, kiểm tra giá trị, gom nhóm, sort sự kiện, tính chuỗi và xuất JSON.
Không cắt 100,000 dòng đầu: có thể làm mất nửa sau chuỗi.
Lệnh có in tiến độ mỗi 250,000 dòng. Không đóng terminal khi đang chạy. Có thể mất vài phút trên WSL/ổ /mnt/e.
Chạy lại cùng thư mục sẽ cập nhật ba file kết quả. Không sửa file log gốc.

## 4. Ba file kết quả

Trong `data/processed/ctu13/scenario-01-tcp/`:

| File | Ai dùng? |
| --- | --- |
| flows.json | Huy Phát đọc chuỗi để phát triển mô hình |
| labels.json | Thành Phát giữ để audit và thiết kế đánh giá |
| summary.json | Cả hai kiểm tra chất lượng, nguồn và tham số |

```bash
python -m json.tool data/processed/ctu13/scenario-01-tcp/summary.json
```

Chú ý `total_rows`, `accepted_rows`, `invalid_selected_rows`, `short_groups`, `exported_groups`, `exported_rows`, `missing_dport_by_protocol_all_rows`, `exported_group_categories`.
TCP gốc dự kiến theo thống kê của bạn là 507,557 dòng; accepted_rows có thể nhỏ hơn nếu có dòng không hợp lệ. Chưa có số nhóm dự đoán.

## 5. Kiểm tra bàn giao và xem một nhóm

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path('data/processed/ctu13/scenario-01-tcp')
payload = json.loads((root / 'flows.json').read_text())
audit = json.loads((root / 'labels.json').read_text())
summary = json.loads((root / 'summary.json').read_text())
assert payload['run_id'] == audit['run_id'] == summary['run_id']
assert payload['schema_version'] == '1.1'
flows = payload['flows']
assert len(flows) == summary['quality']['exported_groups']
assert len({f['flow_id'] for f in flows}) == len(flows)
assert {f['flow_id'] for f in flows} == {a['flow_id'] for a in audit['labels']}
for f in flows:
    n = f['event_count']
    assert n >= summary['source']['min_events']
    assert len(f['timestamps']) == len(f['bytes_sent']) == len(f['relative_times_seconds']) == n
    assert len(f['time_deltas']) == n - 1
    assert all(x >= 0 for x in f['time_deltas'])
    assert f['timestamps'] == sorted(f['timestamps'])
print('ĐẠT: schema, mã nhóm và độ dài các chuỗi khớp.')
print('Số nhóm xuất:', len(flows))
if flows:
    f = flows[0]
    print('Mã nhóm:', f['flow_id'])
    print('Số bản ghi:', f['event_count'])
    print('5 thời điểm đầu:', f['timestamps'][:5])
    print('5 khoảng cách đầu:', f['time_deltas'][:5])
    print('5 lượng byte đầu:', f['bytes_sent'][:5])
PY
```

Đoạn kiểm tra tải JSON lên RAM. Nếu máy thiếu RAM, trước hết chỉ đọc summary.json; báo lại để dùng kiểm tra theo luồng.

## 6. Huy Phát bắt đầu song song

- Đọc `docs/ctu13-contract.md`, hỗ trợ schema 1.1 và ý nghĩa byte/timestamp.
- Chỉ nạp flows.json vào mô hình; labels.json dành cho đánh giá độc lập.
- Kiểm tra hàm nhận chuỗi, trả đúng flow_id, event_count, status, score hoặc null và reason.
- Với quan sát byte theo thời điểm: relative_times_seconds và bytes_sent đều có N phần tử. time_deltas có N-1, không ghép trực tiếp với N byte.
- Ngưỡng 5 chỉ để thử; Huy Phát phải xác định số quan sát tối thiểu phù hợp cho thuật toán. Không báo đây là bộ dữ liệu đủ để tái lập paper.
- Thống nhất cách xử lý khoảng cách 0 và chuỗi toàn 0; không biến chúng thành kết quả benign.

## 7. Git và bàn giao

Commit code, test và quy ước. Kiểm tra .gitignore trước khi add dữ liệu thật; tránh push log/JSON lớn lên GitHub.
Chia sẻ file flows qua kênh lưu file chung hoặc để Huy Phát tái tạo bằng cùng SHA-256 và lệnh.
Ghi kết quả thật vào docs/progress-week-02.md, gồm lệnh, SHA-256, số nhóm, lỗi và hạn chế.
Chưa chốt tuần 2 cho đến khi Huy Phát xác nhận đọc được JSON và hai người chốt quy ước/split/nhãn.

## Hiểu luồng code

1. fingerprint: SHA-256 để đối chiếu file.
2. csv.DictReader: đọc từng dòng; thống kê giao thức/nhãn/cổng thiếu.
3. parse_event: kiểm tra các dòng thuộc phạm vi đã chọn.
4. SQLite: ghi tạm xuống đĩa để không giữ toàn bộ dataset trong RAM.
5. ORDER BY: gom các khóa giống nhau và sắp thời gian; giữ byte và nhãn cùng dòng.
6. itertools.groupby: lần lượt lấy một nhóm; loại nhóm quá ngắn và thống kê.
7. Tính relative_times_seconds, time_deltas; xuất flows không có nhãn, audit nhãn riêng.
8. Kiểm tra tổng số dòng, lưu summary rồi bàn giao.

Đọc quy ước trước khi đổi tham số. Thay phạm vi cần đổi dataset_id/thư mục kết quả để hai người không nhầm phiên bản.
