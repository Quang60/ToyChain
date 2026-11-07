# ToyChain

Hệ thống quản lý chuỗi cửa hàng đồ chơi với **bốn chi nhánh Đông, Tây, Nam, Bắc** và một trung tâm tổng hợp. Mỗi chi nhánh sở hữu dữ liệu giao dịch riêng; trung tâm hợp nhất tồn kho, doanh thu, tài liệu và phản hồi khách hàng.

Đề tài tập trung vào **dữ liệu phân tán** và **hợp nhất dữ liệu có cấu trúc với dữ liệu phi cấu trúc**. Có hai cách chạy: xem giao diện bằng dữ liệu mẫu hoặc chạy toàn bộ dịch vụ bằng Docker Compose.

## Chức năng

- Quản trị: quản lý danh mục, tạo tài khoản, xem báo cáo toàn chuỗi và trạng thái đồng bộ.
- Chi nhánh: nhập hàng, bán hàng, trả theo đơn gốc, điều chỉnh tồn kho, quản lý khách hàng và nhà cung cấp.
- Điều chuyển: xuất kho → đang chuyển → nhận đủ hàng; lưu người xuất và người nhận.
- Tài liệu: tải PDF/PNG/JPG/TXT tối đa 10 MB, liên kết sản phẩm/giao dịch, xem nội dung và tải bản gốc.
- Tìm kiếm hợp nhất: ghép sản phẩm, giá, tồn kho với văn bản tài liệu và phản hồi theo mã định danh.
- ETL: outbox → RabbitMQ → inbox, chống xử lý trùng, giữ sự kiện lỗi để xử lý lại và đối soát định kỳ.

Ba vai trò: **quản trị toàn chuỗi**, **quản lý chi nhánh**, **thu ngân**. Tài khoản do quản trị tạo, không có đăng ký công khai. OCR được để giai đoạn sau; hiện chỉ trích xuất văn bản sẵn có trong PDF/TXT.

## Công nghệ và dữ liệu

| Thành phần | Vai trò |
| --- | --- |
| React 19, TypeScript, Vite | Giao diện web tiếng Việt |
| FastAPI, Python 3.12 | API, nghiệp vụ và worker ETL |
| PostgreSQL 17 | Năm kho dữ liệu: trung tâm và bốn chi nhánh |
| MongoDB 8 | Metadata tài liệu, văn bản trích xuất và phản hồi |
| RabbitMQ 4.1 | Chuyển sự kiện giữa các nút |
| SeaweedFS, API S3 | Lưu tệp gốc |

Các bản ghi liên kết bằng `branch_id`, `product_id` và `order_id`. Giao dịch tại chi nhánh được lưu cùng outbox trong một transaction; báo cáo trung tâm cập nhật sau đồng bộ nên có độ trễ. Chi tiết tại [Kiến trúc](docs/KIEN_TRUC.md).

## Xem giao diện — không cần Docker

Cần **Node.js 22.18+ hoặc 24**. Từ thư mục gốc dự án, chạy trong PowerShell:

```powershell
cd frontend
npm.cmd ci
npm.cmd run preview:ui
```

Mở **http://127.0.0.1:5173**, đăng nhập bằng `admin` / `ToyChainDemo2026!` (đã điền sẵn). Chọn Trung tâm/Đông/Tây/Nam/Bắc để xem từng nút; kim la bàn trên màn hình đăng nhập chỉ theo chi nhánh được chọn.

**Bản xem thử chỉ dùng dữ liệu mẫu, không lưu thay đổi và không chạy backend/ETL thật.** Có thể mở biểu mẫu, tìm kiếm và tải tài liệu TXT mẫu. Giữ terminal mở; nhấn `Ctrl+C` để dừng. Trên macOS/Linux dùng `npm` thay cho `npm.cmd`.

Sau khi đã cài thư viện, cũng có thể chạy `python scripts/manage.py preview` từ thư mục gốc. Nếu cổng 5173 bận, dùng `npm.cmd run preview:ui -- --port 5174` trong `frontend`.

## Chạy toàn bộ hệ thống

Cần **Python 3.12** để chạy script quản lý và **Docker Engine + Compose v2** hoặc **Docker Desktop với Linux containers** (Windows dùng WSL2). Docker build cả frontend lẫn backend; không cần cài Node/Python packages trên máy chủ để chạy cụm.

Từ thư mục gốc:

```powershell
python scripts/manage.py setup
```

Script tạo `.env` với các khóa ngẫu nhiên nếu chưa có, build image và khởi chạy **18 container**. Nó giữ nguyên `.env` hiện có. Dành tài nguyên phù hợp cho năm PostgreSQL, năm API, năm worker và ba dịch vụ chung; mức RAM thực tế chưa được đo.

| Nút | Web | Quản lý | Thu ngân |
| --- | --- | --- | --- |
| Trung tâm | http://localhost:8080 | `admin` | — |
| Đông | http://localhost:8101 | `ql.dong` | `nv.dong` |
| Tây | http://localhost:8102 | `ql.tay` | `nv.tay` |
| Nam | http://localhost:8103 | `ql.nam` | `nv.nam` |
| Bắc | http://localhost:8104 | `ql.bac` | `nv.bac` |

Mật khẩu seed lấy từ `DEMO_PASSWORD` trong `.env`. `admin` đăng nhập được ở mọi nút; tài khoản chi nhánh có thể vào trung tâm để xem dữ liệu thuộc phạm vi mình. Có 16 SKU và phiếu nhập mẫu cho từng chi nhánh; chờ worker đồng bộ trước khi so báo cáo trung tâm. Các tài khoản mẫu phục vụ môi trường đồ án cục bộ.

Các cổng web chỉ mở trên localhost. Chạy trên Codespaces, VPS hoặc nhiều máy cần cấu hình lại địa chỉ các nút và truy cập mạng. Docker trên một máy mô phỏng các nút riêng, chưa chứng minh khả năng chịu lỗi máy vật lý.

## Kiểm thử

Chuẩn bị thư viện kiểm thử cục bộ, không cần Docker:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
npm.cmd ci --prefix frontend
python scripts/manage.py check
```

Lệnh `check` chạy pytest với SQLite cô lập, kiểm thử preview và build TypeScript/Vite. Nó ưu tiên Python trong `.venv`; trên macOS/Linux dùng `python3` và `.venv/bin/python` cho các bước tương ứng.

**Đã kiểm chứng cục bộ: 41 test backend, 4 test preview và build frontend thành công. Kiểm thử Docker thực tế và kiểm tra trực quan bằng trình duyệt còn chờ thực hiện.** Xem phạm vi và kết quả tại [Nhật ký kiểm thử](docs/KIEM_THU.md).

Khi Docker sẵn sàng:

```powershell
python scripts/manage.py integration
```

Kịch bản tạo dữ liệu `TEST-*`, kiểm tra đồng bộ, chống trùng, điều chuyển, bán đồng thời, tài liệu và phân quyền. Sau đó dừng/khởi động lại toàn cụm để kiểm tra dữ liệu PostgreSQL/MongoDB, tệp S3 và sự kiện RabbitMQ còn chờ. Không xóa volume; chạy trong môi trường đồ án không có giao dịch đang sử dụng. Kịch bản đã được cập nhật nhưng chưa chạy trên Docker.

## Lệnh thường dùng

| Lệnh | Mục đích |
| --- | --- |
| `python scripts/manage.py preview` | Web dữ liệu mẫu, không cần backend |
| `npm.cmd run dev` trong `frontend` | Phát triển giao diện, cần API tại `127.0.0.1:8000` |
| `python scripts/manage.py setup` | Tạo cấu hình và khởi chạy Docker |
| `python scripts/manage.py check` | Kiểm thử cục bộ và build |
| `python scripts/manage.py integration` | Kiểm thử toàn cụm Docker, có dừng/khởi động dịch vụ |
| `docker compose logs --tail 100 worker-central` | Xem log ETL trung tâm |
| `docker compose up --build -d --wait` | Build và cập nhật dịch vụ sau khi sửa mã |
| `docker compose down` | Dừng cụm, giữ volume dữ liệu; không thêm `--volumes` nếu cần giữ dữ liệu |

OpenAPI ở `/docs` của từng nút. RabbitMQ Management ở http://localhost:15672, tài khoản `toychain`, mật khẩu từ `RABBIT_PASSWORD`. Các script `.ps1` là wrapper của `manage.py`; nếu PowerShell chặn script thì dùng trực tiếp lệnh Python.

## Cấu trúc

```text
backend/app/          API, nghiệp vụ, ETL, worker, tài liệu
backend/migrations/   Migration Alembic
backend/tests/        Kiểm thử cục bộ
backend/integration/  Kịch bản dịch vụ thật
frontend/src/         Giao diện và dữ liệu preview
frontend/tests/       Kiểm thử preview
scripts/              Lệnh khởi chạy và kiểm tra
docs/                 Kiến trúc, demo, kết quả kiểm thử
compose.yaml          Cụm trung tâm và bốn chi nhánh
```

## Tài liệu và giới hạn

- [Hướng dẫn demo](docs/HUONG_DAN_DEMO.md): các bước xem giao diện và trình diễn nghiệp vụ.
- [Kiến trúc](docs/KIEN_TRUC.md): quyền sở hữu dữ liệu, luồng ETL và hợp nhất tài liệu.
- [Kế hoạch dự án](KE_HOACH_DU_AN.md): phạm vi và quyết định đã chốt.
- [Skill dự án](.agents/skills/toy-chain-distributed/SKILL.md): quy tắc phát triển và kiểm thử.

Thanh toán đang được mô phỏng; chưa có thuế, giảm giá, công nợ, OCR hoặc nhận điều chuyển từng phần. `.env`, dữ liệu cục bộ, môi trường Python, `node_modules`, build và cache không đưa vào Git; giữ chúng trên máy để tiếp tục chạy dự án.
