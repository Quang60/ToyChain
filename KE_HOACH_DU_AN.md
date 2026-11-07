# Kế hoạch đề tài: Hệ thống quản lý chuỗi cửa hàng đồ chơi

## Quyết định đã chốt ngày 06/11/2026

- Bốn chi nhánh: **Đông (`DONG`), Tây (`TAY`), Nam (`NAM`), Bắc (`BAC`)**, cùng một nút trung tâm (`CENTRAL`).
- Ứng dụng web React + TypeScript; API và ETL dùng FastAPI + Python.
- Docker Compose trên một máy: mỗi chi nhánh có API, worker và PostgreSQL riêng; trung tâm có API, worker, PostgreSQL tổng hợp, MongoDB, RabbitMQ và kho tệp tương thích S3.
- PostgreSQL là nguồn chuẩn của giao dịch, tồn kho và danh mục. MongoDB chứa tài liệu, văn bản trích xuất, phản hồi và metadata liên kết. Kho S3 giữ tệp gốc.
- ETL theo sự kiện qua outbox → RabbitMQ → inbox → chuẩn hóa → mô hình đọc trung tâm. ETL theo lịch đối soát dữ liệu nguồn và dữ liệu tổng hợp; không tự ghi đè giao dịch nguồn khi phát hiện sai lệch.
- OCR tiếng Việt để giai đoạn sau. Bản này lưu ảnh/PDF và trích xuất văn bản sẵn có trong PDF/TXT; ảnh và PDF scan được đánh dấu cần OCR. Không tự biến nội dung tài liệu thành giao dịch kho.
- Quyền: quản trị toàn chuỗi, quản lý chi nhánh, thu ngân. Người dùng chỉ thao tác dữ liệu trong phạm vi được cấp.
- Giao diện tiếng Việt, tiền VND lưu số nguyên, thời gian lưu UTC và hiển thị Asia/Ho_Chi_Minh.
- Chức năng bàn giao: danh mục, người dùng, nhà cung cấp/khách hàng, nhập/bán/trả hàng, điều chỉnh kho, điều chuyển, tài liệu, tìm kiếm hợp nhất, báo cáo và giám sát ETL.
- Nghiệm thu: kiểm thử nghiệp vụ và phân quyền; chạy build giao diện; kiểm thử tích hợp PostgreSQL/MongoDB/RabbitMQ/S3; mô phỏng mất kết nối, gửi trùng, khởi động lại và đối soát đủ bốn chi nhánh. Ghi riêng các kiểm thử chưa chạy được do môi trường.

## Bổ sung ngày 07/11/2026: xem giao diện không cần Docker

Thêm chế độ `preview` cho frontend, phục vụ việc xem và góp ý giao diện trước khi cài Docker. Chế độ này dùng dữ liệu mẫu cố định của trung tâm và bốn chi nhánh, hiển thị rõ banner xem thử, không lưu thay đổi hoặc kết nối API/ETL thật. Việc chuyển nút trong bản xem thử chỉ đổi góc nhìn trên cùng một web. Kiến trúc và tiêu chí nghiệm thu hệ thống đầy đủ giữ theo phạm vi đã chốt; kiểm thử mẫu không thay thế kiểm thử dịch vụ thật.

## 1. Mục tiêu và phạm vi

Xây dựng hệ thống quản lý nhiều chi nhánh, có dữ liệu phân tán theo cửa hàng và một góc nhìn hợp nhất cho toàn chuỗi. Hệ thống xử lý dữ liệu có cấu trúc (sản phẩm, tồn kho, đơn hàng, khách hàng, nhân viên) cùng dữ liệu phi cấu trúc (ảnh sản phẩm, hóa đơn/phiếu nhập dạng tệp, phản hồi khách hàng). Bản đầu tiên tập trung vào luồng vận hành có thể trình diễn và đo kiểm; các chức năng mở rộng chỉ thực hiện sau khi chốt yêu cầu.

## 2. Người dùng và nghiệp vụ cốt lõi

| Vai trò | Nhu cầu chính |
| --- | --- |
| Quản trị chuỗi | Quản lý chi nhánh, danh mục, phân quyền và xem báo cáo hợp nhất |
| Quản lý cửa hàng | Theo dõi tồn kho, nhập hàng, điều chuyển và kết quả bán hàng của chi nhánh |
| Nhân viên bán hàng | Tra cứu sản phẩm, lập đơn, nhận thanh toán giả lập, xử lý trả hàng |

Phạm vi MVP: quản lý chi nhánh và tài khoản; danh mục sản phẩm/SKU; nhập và điều chỉnh tồn kho; bán hàng; điều chuyển giữa chi nhánh; tải lên và gắn ảnh/chứng từ vào bản ghi; tìm kiếm sản phẩm và chứng từ; báo cáo doanh thu, tồn kho toàn chuỗi. Chưa tích hợp cổng thanh toán hay đơn vị vận chuyển thật trong MVP.

## 3. Kiến trúc dữ liệu đề xuất

- Mỗi chi nhánh có kho dữ liệu giao dịch riêng cho đơn hàng và biến động tồn kho. Dùng `branch_id` và mã định danh toàn cục để truy vết nguồn. Dịch vụ trung tâm giữ danh mục dùng chung, người dùng, quyền và dữ liệu báo cáo hợp nhất.
- Đồng bộ biến động bằng sự kiện qua hàng đợi. Mỗi giao dịch nghiệp vụ ghi dữ liệu và outbox trong cùng transaction; bộ phát chuyển sự kiện sang hàng đợi; bộ nhận xử lý idempotent và cập nhật mô hình đọc trung tâm. Cho phép chi nhánh tiếp tục hoạt động khi mất kết nối rồi đồng bộ lại.
- Dữ liệu phi cấu trúc nằm trong object storage; cơ sở dữ liệu lưu metadata, checksum, loại tệp, chi nhánh sở hữu, đối tượng liên kết, quyền truy cập và trạng thái xử lý. Văn bản trích xuất từ chứng từ hoặc phản hồi được chuẩn hóa thành chỉ mục tìm kiếm; tệp gốc vẫn được giữ để đối chiếu.
- Báo cáo toàn chuỗi có độ trễ đồng bộ được hiển thị bằng `last_synced_at`. Tồn kho bán tại chi nhánh lấy từ dữ liệu giao dịch của chính chi nhánh. Điều chuyển dùng trạng thái xuất, đang vận chuyển, nhận; không trừ/cộng hai đầu bằng một thao tác phân tán giả định nguyên tử.
- Xung đột: danh mục trung tâm là nguồn chuẩn; sự kiện bán hàng và biến động tồn kho là bất biến, không ghi đè bằng "bản mới nhất"; sự kiện trùng được loại bằng `event_id`; chỉnh sửa nghiệp vụ tạo sự kiện bù trừ và lưu audit.

Stack đã chốt: React/TypeScript, FastAPI/Python, PostgreSQL, MongoDB, RabbitMQ, kho tệp tương thích S3 và Docker Compose. Tìm kiếm hợp nhất thực hiện tại API, liên kết qua product_id, branch_id, order_id và document_id. Chưa cần OpenSearch hay Airflow cho quy mô này.

## 4. Mô hình dữ liệu khởi đầu

Mô hình triển khai: cấu hình cố định bốn chi nhánh; bảng `users` lưu vai trò và phạm vi; `products` chứa một SKU mỗi sản phẩm; `partners` quản lý khách hàng/NCC; `transactions` cùng snapshot dòng hàng biểu diễn nhập/bán/trả/điều chỉnh; `movements` và `stock` là sổ biến động và số dư; `transfers` là điều chuyển; `outbox`, `inbox`, `dead_letters`, `control`, `reconciliations` phục vụ ETL. MongoDB có collection `documents` và `feedback`. Mọi giao dịch có `branch_id`, thời gian UTC, tác nhân và ID ổn định. Tệp gốc nằm trong S3, metadata MongoDB chỉ lưu liên kết và nội dung trích xuất.

## 5. Lộ trình thực hiện và tiêu chí hoàn thành

| Giai đoạn | Sản phẩm cần giao | Kiểm chứng |
| --- | --- | --- |
| 1. Chốt yêu cầu | Use case, quy tắc nghiệp vụ, sơ đồ triển khai, quyết định stack | Thống nhất phạm vi và kịch bản trình diễn |
| 2. Nền tảng | Schema, xác thực/phân quyền, quản lý chi nhánh, danh mục | Tạo và truy vấn dữ liệu nhiều chi nhánh đúng quyền |
| 3. Giao dịch phân tán | Nhập hàng, bán hàng, tồn kho, điều chuyển, outbox/inbox | Không mất/nhân đôi giao dịch khi gửi lại sự kiện hoặc ngắt kết nối |
| 4. Dữ liệu hỗn hợp | Tải tệp, metadata, gắn tệp với nghiệp vụ, trích xuất và tìm kiếm | Tra cứu một sản phẩm/đơn hàng thấy cả bản ghi và tệp liên quan |
| 5. Hợp nhất và báo cáo | Mô hình đọc toàn chuỗi, doanh thu/tồn kho, dấu thời gian đồng bộ | Số liệu khớp sự kiện nguồn sau khi đồng bộ hoàn tất |
| 6. Hoàn thiện | Kiểm thử, seed data, tài liệu vận hành, video/demo | Chạy lại được bằng hướng dẫn và dữ liệu mẫu |

## 6. Kịch bản kiểm thử bắt buộc

1. Bốn chi nhánh Đông, Tây, Nam, Bắc cùng bán các SKU khác nhau và cùng một SKU; số liệu cục bộ và toàn chuỗi khớp sau đồng bộ.
2. Ngắt kết nối một chi nhánh, tạo giao dịch, kết nối lại; sự kiện tồn đọng được phát và báo cáo cập nhật.
3. Gửi lại cùng một sự kiện nhiều lần; tồn kho và doanh thu chỉ thay đổi một lần.
4. Điều chuyển hàng qua các trạng thái; số lượng xuất, đang chuyển và nhận được đối soát.
5. Tải ảnh/chứng từ, liên kết vào sản phẩm/phiếu nhập, tìm kiếm qua metadata hoặc văn bản trích xuất, kiểm tra quyền truy cập tệp.

## 7. Các yêu cầu có thể bổ sung sau

- OCR tiếng Việt và quy trình kiểm duyệt kết quả nhận dạng.
- Triển khai nhiều máy thật, sao lưu tự động và cơ chế HA cho dịch vụ trung tâm.
- Thời hạn và mẫu báo cáo/tiêu chí chấm của môn học khi người dùng cung cấp.

Các bổ sung trên không ngăn triển khai phạm vi đã chốt. Docker nhiều container trên một máy chỉ mô phỏng phân tán, chưa kiểm chứng chịu lỗi máy vật lý.
