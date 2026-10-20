# Phân công và quyền sửa file

| Phần | Chủ trì | Người review |
| --- | --- | --- |
| `src/data/`, `src/baselines/`, `src/evaluation/` | A | B |
| `data/sample/`, `tests/data/`, `tests/evaluation/`, `tests/baselines/` | A | B |
| `src/models/`, `src/runner.py`, `configs/`, `requirements.txt`, `tests/models/` | B | A |
| README, báo cáo dữ liệu và kết quả | A | B |
| Phương pháp, cấu hình, giới hạn tái lập | B | A |
| `docs/data-contract.md`, `docs/experiment-plan.md` | A giữ file, cả hai thống nhất | B |
| `.github/`, quy trình nhóm | A giữ file, cả hai thống nhất | B |

A là bạn đang phụ trách dữ liệu và đánh giá. B là thành viên còn lại. Thay A/B bằng tên thực tế trong tài liệu khi nhóm thống nhất. Tài khoản CODEOWNERS cần điền riêng, không tự suy ra từ tên người.

File do một người giữ không có nghĩa người kia không được đề xuất sửa; thay đổi đi qua pull request để hai phần không lệch giao diện.
