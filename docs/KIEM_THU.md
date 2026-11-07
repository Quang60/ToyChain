# Nhật ký kiểm thử — 07/11/2026

## Kết quả cục bộ

| Kiểm tra | Kết quả |
| --- | --- |
| `python scripts/manage.py check` — backend | **41 passed** trong 19,08 giây; SQLite cô lập |
| Kiểm thử dữ liệu preview | **4 passed** |
| TypeScript + Vite production build | Thành công với Vite 6.4.5 |
| Dependency backend — lượt kiểm tra trước | `pip check`: không có dependency bị thiếu/xung đột |
| Dependency frontend — lượt cài bản vá trước | `npm audit`: 0 cảnh báo tại thời điểm kiểm tra đó |

Kiểm thử backend bao gồm xác thực/phạm vi chi nhánh, quyền thu ngân, chống gửi trùng, giá từ máy chủ, rollback khi thiếu hàng, giới hạn trả hàng, điều chỉnh có lý do, điều chuyển/nhận trùng, phân phối danh mục/tài khoản, replay event và migration/seed sau restart. Kiểm thử tài liệu xác minh UTF-8, kích thước/định dạng, PDF không có text và ảnh không được giả nhận dạng OCR.

17 trường hợp hồi quy mới bao phủ JSON sai cấu trúc (`null`, mảng, chuỗi, số, boolean, JSON hỏng), trường envelope không hợp lệ, ghi dead letter trước ACK, xử lý được thông điệp hợp lệ tiếp theo, không ACK khi DB lỗi và rollback nếu commit dead letter thất bại. Kênh RabbitMQ được mô phỏng trong các test này; không coi đây là kết quả broker thật.

Kiểm thử preview kiểm tra số liệu bốn chi nhánh, tồn/doanh thu nhất quán với giao dịch mẫu, tìm kiếm hợp nhất, tải tài liệu đúng phạm vi và từ chối lưu thay đổi. Preview không dùng dịch vụ dữ liệu thật.

## Các điểm đã sửa sau rà soát

| Vấn đề | Thay đổi | Bằng chứng / giới hạn |
| --- | --- | --- |
| Worker lỗi khi nhận JSON `null`/`[]` | Kiểm tra envelope trước khi truy cập trường/ID; lỗi dữ liệu được giữ trong `dead_letters` | Các kiểm thử hồi quy mới đã qua; lỗi dịch vụ tạm thời vẫn không ACK |
| Nút đăng xuất bị ẩn ở màn hình hẹp | Thêm nút có nhãn truy cập trên thanh trên; bổ sung nhãn cho menu thu gọn | TypeScript/build qua; cần kiểm tra trực quan trên trình duyệt |
| Script PowerShell bỏ sót test preview và dùng Python/thư mục tạm khác | `setup.ps1`, `check.ps1`, `test-stack.ps1` gọi chung `manage.py` | Lệnh Python đã chạy; chưa chạy các `.ps1` do execution policy Windows |
| Kiểm thử gửi trùng chỉ chờ 3 giây | Gửi sự kiện đánh dấu phía sau cùng hàng đợi và đợi Inbox xác nhận | Mã kịch bản đã cập nhật, chờ Docker |
| Kiểm thử phục hồi chỉ restart API/worker chi nhánh | Dừng/khởi động toàn cụm; kiểm tra số dư, metadata, SHA-256 tệp gốc, sự kiện bền vững trong RabbitMQ và heartbeat cả năm worker | Chưa chạy trên dịch vụ thật |

README đã được sắp xếp lại theo chức năng, công nghệ, cách chạy, lệnh kiểm thử và tài liệu. Cấu hình cá nhân, bí mật, dữ liệu mẫu sinh trên máy, build và cache được loại khỏi Git; vẫn giữ mã nguồn, lockfile, migration, test và tài liệu cần cho đề tài.

## Chờ kiểm tra với Docker và trình duyệt

- Build image và khởi chạy đủ 18 service; kiểm tra kết nối PostgreSQL, MongoDB, RabbitMQ, SeaweedFS.
- Bán đồng thời trên PostgreSQL, gửi trùng qua RabbitMQ, gián đoạn đồng bộ, đối soát bốn chi nhánh.
- Khởi động lại toàn cụm và kiểm tra dữ liệu/tệp/sự kiện theo kịch bản cập nhật.
- Thao tác đăng nhập/đăng xuất, la bàn năm lựa chọn, biểu mẫu và tải tệp trên desktop/mobile.

Người dùng yêu cầu để kiểm thử Docker lại sau vì máy chưa có Docker. Công cụ trình duyệt hiện chưa kết nối được browser host/native pipe. Không tuyên bố đã nghiệm thu các phần này chỉ từ build, HTTP hoặc SQLite.

Pytest còn một `DeprecationWarning` từ Starlette/AnyIO về `BlockingPortal`, không làm thất bại test. Thư mục tạm của `check` được tạo riêng trong `.tools` và dọn sau khi dùng để tránh lỗi quyền tại thư mục tạm dùng chung của Windows.

## Cách tiếp tục nghiệm thu

```powershell
python scripts/manage.py setup
python scripts/manage.py integration
```

Kịch bản integration tạo SKU `TEST-*`, tạm dừng đồng bộ trung tâm để giữ một sự kiện trong RabbitMQ, sau đó dừng/khởi động toàn cụm và bật lại đồng bộ. Không chạy khi có người đang thực hiện giao dịch. Nếu bị ngắt giữa các bước, khởi động cụm rồi đăng nhập trung tâm, vào **Đồng bộ & ETL → Tiếp tục đồng bộ** trước khi sử dụng bình thường. Không xóa volume. Chạy lại `integration` từ đầu để tạo bộ dữ liệu kiểm thử mới.

Lưu kết quả từng bước và log API/worker nếu có lỗi. Việc có mã kiểm thử không đồng nghĩa với đã vượt qua kiểm thử trên hạ tầng thật.
