# Khảo sát ba nhóm CTU-13 Scenario 1 — Thành Phát

Nguồn: `data/processed/ctu13/scenario-01-tcp/flows.json` và `labels.json`, cùng `run_id` theo quy ước tại `docs/ctu13-contract.md`. Đây là khảo sát minh họa ba nhóm được chọn; **không đại diện cho toàn bộ 11.247 nhóm đã xuất**.

## Chạy lại

Từ thư mục gốc repository, cài dependency theo `requirements.txt` nếu môi trường chưa có, rồi chạy:

```bash
python3 -m src.analysis.plot_flows
```

Script dùng backend Matplotlib `Agg`, ghi ba PNG vào `outputs/figures/ctu13-scenario01/` và bảng đầy đủ độ chính xác vào `outputs/ctu13-scenario01-flow-statistics.csv`. Không cần màn hình đồ họa. File đầu vào không bị sửa.

## Quy tắc chọn

1. Lấy đúng nhóm TCP từ `147.32.84.165` đến `31.192.109.167:80`.
2. Lấy đúng nhóm TCP từ `147.32.84.165` đến `173.192.170.88:80`.
3. Trong các nhóm `category=normal`, TCP và ít nhất 20 bản ghi, chọn `event_count` gần 53 nhất; nếu cùng độ gần, chọn `flow_id` nhỏ nhất theo thứ tự chữ. Không dùng mức độ đều đặn để chọn. Tập này có 81 nhóm đủ điều kiện; nhóm được chọn có đúng 53 bản ghi. Nếu không có nhóm normal đủ điều kiện, script dừng với thông báo rõ và không thay bằng Background.

## Số liệu thực tế

`duration_seconds` là thời điểm tương đối cuối trừ thời điểm đầu. Các thống kê delta dùng toàn bộ N−1 khoảng cách. `population_std_delta` là độ lệch chuẩn tổng thể; `timing_cv = population_std_delta / mean_delta`. Nếu trung bình bằng 0, CSV để trống CV và điền `timing_cv_reason=mean_delta_is_zero`.

| Nhóm (nguồn → đích) | Category | Số bản ghi | Thời lượng (s) | Delta nhỏ nhất / trung vị / lớn nhất (s) | Delta TB (s) | Độ lệch chuẩn tổng thể (s) | CV | Dòng có CC |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `147.32.84.165 → 31.192.109.167:80/tcp` | botnet | 53 | 7.634,315090 | 3,173239 / 123,463505 / 424,011897 | 146,813752 | 83,088180 | 0,565943 | 53 |
| `147.32.84.165 → 173.192.170.88:80/tcp` | botnet | 266 | 16.662,323259 | 0,000012 / 30,143364 / 1.319,206391 | 62,876692 | 126,652951 | 2,014307 | 221 |
| `147.32.84.164 → 194.79.52.199:80/tcp` | normal | 53 | 7.952,284625 | 0,000004 / 0,000068 / 6.868,000934 | 152,928550 | 949,394421 | 6,208091 | 0 |

Hình tương ứng:

- [Nhóm đến 31.192.109.167](../outputs/figures/ctu13-scenario01/target-01_147.32.84.165_31.192.109.167_80_tcp.png)
- [Nhóm đến 173.192.170.88](../outputs/figures/ctu13-scenario01/target-02_147.32.84.165_173.192.170.88_80_tcp.png)
- [Nhóm normal đối chiếu](../outputs/figures/ctu13-scenario01/normal_147.32.84.164_194.79.52.199_80_tcp.png)

Mỗi hình vẽ toàn bộ `time_deltas` theo chỉ số khoảng thời gian ở trên, và toàn bộ `bytes_sent` theo `relative_times_seconds` ở dưới. Cả hai trục dùng thang tuyến tính; các giá trị cực trị không bị cắt.

## Quan sát và giới hạn

- Nhóm 31.192.109.167 có 32/52 khoảng cách trong khoảng 115–125 giây, nhưng cũng có khoảng cách 3,17 và 424,01 giây. Toàn bộ 53 bản ghi có nhãn gốc chứa `CC53`; byte nguồn nằm trong khoảng 391–1.050.
- Nhóm 173.192.170.88 có trung vị khoảng cách 30,14 giây và cực đại 1.319,21 giây; 221 bản ghi chứa `CC16`, 45 bản ghi còn lại có nhãn `TCP-Attempt`. Byte nguồn nằm trong khoảng 186–2.015. Không thể gọi cả nhóm là C2 đã xác minh chỉ từ nhãn này.
- Nhóm normal được chọn theo độ dài, với trung vị delta rất nhỏ (0,0000675 giây) nhưng cực đại 6.868,00 giây; byte nguồn từ 206 đến 56.994. CV cao phản ánh sự phân tán lớn trong chuỗi này, không phải đặc điểm đại diện cho mọi nhóm normal.

Các hình biểu diễn **bản ghi flow Argus**, không phải từng packet hay HTTP request. `SrcBytes` giữ ý nghĩa trường nguồn; không suy ra mọi điểm là byte do client gửi. Nhãn CC là chú thích trong dataset, **chưa phải ground truth beaconing**. Thời điểm có thể chịu ảnh hưởng cách Argus xuất flow; các đồ thị này chỉ hỗ trợ khảo sát, không chứng minh phát hiện mã độc.
