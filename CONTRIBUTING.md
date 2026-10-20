# Quy trình làm việc của nhóm

## Phân công và thay đổi chung

- A giữ dữ liệu, baseline, đánh giá và phần báo cáo tương ứng.
- B giữ mô hình, cấu hình, lệnh chạy và phần báo cáo tương ứng.
- Mỗi người viết test cho phần của mình; người kia kiểm tra ý nghĩa kết quả.
- `docs/data-contract.md` là quy ước chung. Đề xuất thay đổi bằng pull request, cập nhật phiên bản schema và bên sử dụng cùng lúc.
- Không cùng sửa notebook hoặc file báo cáo tổng. Viết phần riêng, ghép vào mốc đã thống nhất.

## Một task từ đầu đến cuối

1. Tạo issue theo mẫu Task, có người nhận, sản phẩm và điều kiện hoàn thành.
2. Cập nhật `main` bằng `git pull --ff-only` khi working tree sạch.
3. Tạo nhánh `feature/...`, `fix/...` hoặc `docs/...`.
4. Làm một thay đổi có phạm vi rõ; không kèm dữ liệu lớn hoặc kết quả giả.
5. Chạy `python -m unittest discover -s tests -v` và `python -m src.runner demo` nếu liên quan pipeline.
6. Push nhánh và tạo pull request; ghi cách kiểm tra cùng giới hạn còn lại.
7. Người còn lại review. Merge khi code và tài liệu thống nhất, CI thành công.

Chưa có quy tắc bảo vệ nhánh tự động cho đến khi người quản lý bật trên GitHub.

## Commit và dữ liệu

- Ví dụ: `feat(data): add CTU-13 adapter`, `fix(models): handle short sequences`.
- Dùng UTF-8 và xuống dòng LF; `.gitattributes` đã quy định.
- Không commit `.venv`, dữ liệu gốc lớn, PCAP, token, khóa riêng, mô hình đã lưu.
- Dữ liệu mẫu nhỏ không chứa thông tin riêng có thể commit trong `data/sample/`.
- Kết quả thực nghiệm cuối được trích vào báo cáo kèm run ID; không đẩy mọi output tự sinh lên Git.
- Khi có conflict, đọc thay đổi của cả hai; chạy lại kiểm tra sau khi giải quyết. Không dùng force push để tránh phải giải quyết conflict.

## Nhịp phối hợp

Mỗi tuần 30 phút chốt việc, 30 phút kiểm tra điểm nghẽn và 60 phút review/ghép code. Ghi giờ thực tế, điều chỉnh tác vụ nếu một người quá tải. Hai người đều phải giải thích được toàn bộ pipeline khi bảo vệ.
