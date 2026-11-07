# Kịch bản trình diễn

## Xem giao diện khi chưa có Docker

### 1. Khởi chạy web

Trong VS Code, mở **Terminal → New Terminal**. Từ thư mục gốc dự án chạy:

```powershell
python scripts/manage.py preview
```

Giữ terminal đang chạy, mở **http://127.0.0.1:5173** bằng Chrome hoặc Edge. Nếu web đã chạy từ trước thì chỉ cần tải lại trang (`Ctrl+R`), không cần khởi chạy thêm.

Máy hiện tại đã có Node.js và thư viện frontend. Nếu chạy trên máy mới, cần Node.js và chạy `npm.cmd ci` trong thư mục `frontend` trước; cũng có thể dùng `npm.cmd run preview:ui` từ thư mục đó để chạy web mà không dùng Python. Nếu cổng 5173 đang bận bởi ứng dụng khác, chạy `npm.cmd run preview:ui -- --port 5174` trong `frontend`, rồi mở http://127.0.0.1:5174.

### 2. Xem la bàn trên màn hình đăng nhập

Nếu trang mở thẳng vào dashboard, bấm biểu tượng **Đăng xuất** ở góc trên bên phải, cạnh ô chọn chi nhánh, để quay lại đăng nhập. Nút này hiển thị trên cả desktop và màn hình hẹp.

Chọn các nút dưới biểu mẫu đăng nhập, đối chiếu kim với hướng được chọn:

| Nút được chọn | La bàn |
| --- | --- |
| Trung tâm | Không có kim, hiện biểu tượng kết nối ở giữa và nhãn Trung tâm |
| Đông | Đầu kim vàng chỉ sang phải, chữ ĐÔNG sáng hơn |
| Tây | Đầu kim vàng chỉ sang trái, chữ TÂY sáng hơn |
| Nam | Đầu kim vàng chỉ xuống dưới, chữ NAM sáng hơn |
| Bắc | Đầu kim vàng chỉ lên trên, chữ BẮC sáng hơn |

La bàn hiện ở phần minh họa bên trái trên desktop; ở màn hình hẹp, la bàn nằm phía trên biểu mẫu. Trong bản xem thử, chọn chi nhánh đổi tham số `?node=...` trên cùng cổng 5173. Trong hệ thống Docker, chọn chi nhánh mở đúng web của nút đó (8080/8101–8104).

### 3. Đăng nhập và trình diễn các màn hình

Chọn **Trung tâm**, giữ tài khoản điền sẵn **`admin`** / **`ToyChainDemo2026!`**, rồi nhấn **Vào bản xem thử**.

1. **Tổng quan**: xem số liệu mẫu của cả bốn chi nhánh.
2. **Sản phẩm / Tồn kho / Giao dịch / Điều chuyển**: xem danh mục, lọc danh sách và mở chi tiết.
3. **Tài liệu & tìm kiếm**: gõ `chứng nhận an toàn`, bấm **Tìm hợp nhất** để thấy sản phẩm LEGO-001, tồn kho từng chi nhánh và tài liệu liên quan. Bấm **Xem nội dung** hoặc tải TXT mẫu.
4. Chọn **Đông, Tây, Nam hoặc Bắc** ở góc trên bên phải. Mở **Giao dịch → Tạo giao dịch** để xem biểu mẫu.
5. Chọn lại **Trung tâm** để xem **Nhân viên**, **Phản hồi**, **Đồng bộ & ETL**.

Banner màu vàng đánh dấu bản xem thử. Dữ liệu mẫu có mốc 06/11/2026, không thay đổi theo thời gian. Các nút lưu/tải lên/đồng bộ báo rằng thao tác chưa được thực hiện; không dùng bản này để kiểm chứng ETL hoặc lưu giao dịch.

### 4. Dừng web hoặc chạy kiểm tra

Quay lại terminal đang chạy web và nhấn `Ctrl+C` để dừng. Khi cần mở lại, chạy lại lệnh ở bước 1.

Để kiểm thử mã, mở terminal khác ở thư mục gốc rồi chạy `python scripts/manage.py check`. Lệnh này chạy kiểm thử backend, kiểm thử dữ liệu xem thử và build frontend; không cần Docker. Demo với giao dịch được lưu và ETL thật cần hệ thống đầy đủ bên dưới.

## Chuẩn bị demo hệ thống đầy đủ bằng Docker

Chạy `python scripts/manage.py setup`, đăng nhập trung tâm bằng admin, kiểm tra cả bốn chi nhánh có dữ liệu. Mở từng nút ở 8080/8101/8102/8103/8104. Mật khẩu nằm trong DEMO_PASSWORD của `.env`. Đợi worker đồng bộ phiếu nhập mẫu trước khi so số liệu.

## Luồng nghiệp vụ

1. Trung tâm: thêm sản phẩm SKU `DEMO-001`, giá 250.000 VND. Vài giây sau, làm mới danh mục tại cả bốn chi nhánh để thấy bản ghi mới.
2. Đông: mở Giao dịch → Tạo giao dịch → Nhập hàng, nhập 10 sản phẩm, giá nhập 150.000. Mở Tồn kho để kiểm tra.
3. Đông: bán 2 sản phẩm. Giá bán lấy từ danh mục. Kiểm tra kho còn 8 và doanh thu tăng 500.000 VND; làm mới trung tâm sau khi sự kiện được xử lý.
4. Thử bán 100 sản phẩm. Hệ thống phải báo không đủ tồn kho, số lượng và doanh thu giữ nguyên.
5. Quản lý Đông: trả 1 sản phẩm từ đơn gốc. Kho tăng 1, doanh thu thuần giảm 250.000. Thử trả vượt số lượng đã mua để thấy lỗi kiểm tra.
6. Đông: điều chuyển 3 sản phẩm sang Tây. Kho Đông giảm ngay, trạng thái Đang chuyển. Tây nhận đủ; kho Tây tăng, trạng thái hai đầu cập nhật Đã nhận.

## Luồng ETL và dữ liệu hỗn hợp

1. Đông: mở Đồng bộ & ETL, tạm dừng đồng bộ. Đây là mô phỏng dừng worker xử lý, không phải rút dây mạng thật.
2. Bán thêm 1 sản phẩm tại Đông. Giao dịch và tồn kho cục bộ cập nhật; outbox chờ gửi tăng; trung tâm chưa nhận giao dịch mới. Tây/Nam/Bắc vẫn làm việc.
3. Tiếp tục đồng bộ; chờ vài giây và làm mới trung tâm. Outbox được gửi, tồn kho/doanh thu hợp nhất cập nhật. Xem kết quả đối soát sau một lượt định kỳ.
4. Trung tâm: tải một TXT UTF-8 chứa câu “Chứng nhận an toàn DEMO-001”, chọn liên kết sản phẩm và chi nhánh Đông. Worker chuyển trạng thái sang Đã trích xuất.
5. Tìm “chứng nhận an toàn” bằng Tìm hợp nhất. Kết quả phải có tài liệu, sản phẩm, giá và tồn kho các chi nhánh.
6. Tải một ảnh JPG/PNG thật hoặc PDF scan. Trạng thái phải là Cần OCR, nội dung chưa được nhận dạng. Chức năng OCR được dành cho giai đoạn sau.
7. Đăng nhập trung tâm bằng `ql.tay`; kiểm tra tài liệu chỉ thuộc Đông không xuất hiện. Đăng nhập chi nhánh bằng `nv.dong`; chức năng nhập hàng/điều chỉnh/điều chuyển không được phép.

## Kịch bản lỗi dịch vụ thật

Trong môi trường đồ án, dừng worker một chi nhánh bằng `docker compose stop worker-dong`, tạo giao dịch cục bộ rồi khởi động `docker compose start worker-dong`. Để kiểm tra broker gián đoạn, dùng `docker compose stop rabbit`, tạo giao dịch rồi `docker compose start rabbit`; chờ worker kết nối lại và đối soát.

`python scripts/manage.py integration` (hoặc wrapper `scripts/test-stack.ps1`) kiểm tra gửi trùng đã được tiêu thụ, bán đồng thời, tài liệu thật trên MongoDB/S3 và phục hồi sau khi dừng/khởi động toàn cụm. Kịch bản giữ một sự kiện trong RabbitMQ qua lần restart và kiểm tra lại SHA-256 của tệp gốc. Nó tạm dừng đồng bộ trung tâm trước restart và bật lại ở bước kiểm tra cuối; nếu bị ngắt, hãy bật lại đồng bộ trung tâm trước khi sử dụng bình thường. Kịch bản đã được cập nhật nhưng chưa chạy trên Docker; xem `docs/KIEM_THU.md`.
