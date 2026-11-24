# TU02 – Triển khai Ubuntu Server 24.04 LTS

Đích: máy 2 vCPU/2 GB RAM, Docker Engine 27 trở lên, Compose v2.17 trở lên,
Python 3.12, Gunicorn 3 worker, PostgreSQL 16. Các lệnh dưới đây chạy bằng Bash
trên Ubuntu. Windows hiện chưa chạy container vì không có Docker Desktop;
CI Ubuntu 24.04 đã kiểm chứng build, health, login và giữ DB/MEDIA sau down/up.
Kết quả cụ thể: [TU02.md](TU02.md).

## 1. Cài Docker trên máy mới

Theo [Docker Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Các bước sau dùng `sudo docker`, không yêu cầu đưa tài khoản vào nhóm docker.

## 2. Clone và tạo cấu hình riêng

```bash
git clone --branch tu02-trien-khai-docker https://github.com/MrTroll219/sales-and-inventory-management.git
cd sales-and-inventory-management
umask 077
cp .env.example .env
sudo docker run --rm -i -v "$PWD:/work" -w /work python:3.12-slim python - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text()
s = s.replace('SECRET_KEY=\n', 'SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
s = s.replace('DB_PASSWORD=\n', 'DB_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
p.write_text(s)
PY
chmod 600 .env
```

Không commit hoặc đưa `.env` vào log. Ví dụ mặc định cố ý dùng HTTP nội bộ:
`DEBUG=false`, `DJANGO_SECURE_SSL=false`, bind `127.0.0.1:8000`. Truy cập từ máy khác
qua SSH tunnel `ssh -L 8000:127.0.0.1:8000 user@server`, rồi mở localhost:8000.
Đây là ngoại lệ lab; cấu hình HTTPS công khai ở mục 4.

## 3. Khởi động và kiểm tra

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build --wait --wait-timeout 180
sudo docker compose ps
curl -I http://127.0.0.1:8000/accounts/login/
sudo docker compose exec web python manage.py createsuperuser
sudo docker compose logs --tail=100 web
```

`db`, `web` và `nginx` phải healthy; login qua nginx trả 200. Cổng public 8000
(WEB_PORT) được publish bởi nginx:80; web chỉ expose 8000 trong mạng Compose.
Entrypoint đợi DB healthy thông qua
Compose, kiểm tra dữ liệu Profile cũ bằng lệnh chỉ đọc `check_profile_data`, migrate
rồi exec Gunicorn dưới user `app` UID 10001. DB trống được bỏ qua bước kiểm tra bảng
chưa tồn tại. Nếu có email trùng/tên quá dài, dừng và xử lý theo [TU01.md](TU01.md),
không tự sửa dữ liệu.

Static được thu thập đúng một lần **lúc build image** với key sinh tạm chỉ cho
lệnh đó; khi khởi động không chạy collectstatic. WhiteNoise phục vụ static đã build.
`pgdata` chứa DB; `media` mount `/app/media`, độc lập với image. Tệp tải lên được
giữ qua down/up. Service `nginx:1.27-alpine` đọc volume media tại `/srv/media:ro`,
phục vụ `/images/` bằng alias; phần còn lại (kể cả `/static/`) proxy tới web:8000.
Nginx truyền Host, X-Forwarded-For và X-Forwarded-Proto. Cấu hình ở
`nginx/default.conf`; kiểm tra bằng `sudo docker compose exec nginx nginx -t`.
Nginx hiện nghe HTTP, TLS vẫn kết thúc tại proxy tin cậy bên ngoài.

Entrypoint copy `static/images/profile_pics/default.jpg` vào volume nếu chưa có;
không ghi đè file đã tồn tại. Kiểm tra ảnh mặc định:

```bash
curl -I http://127.0.0.1:8000/images/profile_pics/default.jpg
```

Mong đợi 200, Content-Type image/jpeg. Việc chỉ đọc MEDIA của nginx không thay đổi
quyền ghi MEDIA của web. Nginx không liệt kê thư mục.

### Chuyển ảnh upload cũ

Sao lưu trước và xác định đúng thư mục upload, giữ nguyên tên tương đối trong DB.
Ảnh Profile cũ dưới `static/images/profile_pics/` cần chuyển sang
`media/profile_pics/`. Không chuyển cả logo/static trang trí vào MEDIA.
Ví dụ copy ảnh Profile từ image hiện tại vào volume, giữ file đích có sẵn:

```bash
sudo docker compose run --rm --no-deps --entrypoint sh web -c 'mkdir -p /app/media/profile_pics; cp -an /app/static/images/profile_pics/. /app/media/profile_pics/'
```

Nếu ảnh cũ nằm ngoài image, đưa bản sao lưu đã kiểm tra vào đúng volume tương ứng;
không xóa nguồn cho đến khi kiểm tra URL `/images/<đường-dẫn-trong-DB>` trả 200.
Thư mục upload khác phải được xác định rồi copy riêng theo cùng nguyên tắc.
Không tự cập nhật đường dẫn DB hoặc ghi đè file trùng tên.

Chạy local không Docker vẫn giữ `static()` trong store/urls.py khi DEBUG=True.
Tạo MEDIA_ROOT/profile_pics rồi copy ảnh cũ sang đó; với MEDIA_ROOT mặc định,
chạy `python scripts/seed_default_media.py` để tạo ảnh mặc định còn thiếu.

Chứng minh persistence trên dữ liệu thử: tạo sản phẩm và upload tệp, chạy các lệnh
dưới đây rồi kiểm tra lại sản phẩm/tệp:

```bash
sudo docker compose down
sudo docker compose up -d --wait --wait-timeout 180
sudo docker compose ps
```

Không thêm `-v` khi down môi trường cần giữ dữ liệu.

## 4. HTTPS production và check --deploy

Sửa `.env` theo domain thực, key ngẫu nhiên dài ít nhất 50 ký tự:

```dotenv
DEBUG=false
ALLOWED_HOSTS=inventory.example.org
CSRF_TRUSTED_ORIGINS=https://inventory.example.org
DJANGO_SECURE_SSL=true
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
BIND_ADDRESS=127.0.0.1
```

`INCLUDE_SUBDOMAINS`/`PRELOAD` chỉ bật sau khi xác nhận chính sách HTTPS của domain
và mọi subdomain. Bằng chứng 0 issues sử dụng hai cờ này; để false sẽ xuất hiện
W005/W021. Tăng HSTS lên `31536000` khi đã chắc chắn HTTPS hoạt động ổn định;
preload thực sự còn cần đáp ứng chính sách/trình đăng ký preload bên ngoài.

Reverse proxy TLS tin cậy phía trước nginx phải xóa header do client gửi và tự đặt
`X-Forwarded-Proto: https`, giữ Host đúng domain, chặn truy cập trực tiếp tới Gunicorn.
Nginx giữ scheme http/https từ header này, nếu thiếu thì dùng scheme kết nối.
Không mở cổng nginx cho client không tin cậy khi dùng header từ proxy bên ngoài;
giữ bind loopback hoặc giới hạn mạng/firewall chỉ cho proxy TLS.
Khi SSL=true, settings bật redirect HTTPS, cookie session/CSRF secure, HSTS và
`SECURE_PROXY_SSL_HEADER`. Không dùng cờ này với proxy không kiểm soát header.
Xem [Django proxy SSL header](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header).

```bash
sudo docker compose up -d --wait
sudo docker compose exec web python manage.py check --deploy
```

Mong đợi `System check identified no issues (0 silenced).` Đây là kiểm tra cấu hình,
không thay thế kiểm tra chứng chỉ/proxy/TLS thực tế. Lab SSL=false cố ý chưa đạt
các kiểm tra yêu cầu HTTPS, vẫn giữ DEBUG=false và key mạnh.

## 5. Biến môi trường và tương thích

Biến process ưu tiên hơn `.env` (`load_dotenv(override=False)`). `DJANGO_ENV_FILE`
cho phép chọn file khác. SECRET_KEY luôn bắt buộc, kể cả DEBUG=true; khi DEBUG=false
phải >=50 ký tự, >=5 ký tự khác nhau và không có tiền tố django-insecure-.
Danh sách host/origin tách bằng dấu phẩy, bỏ khoảng trắng và phần tử rỗng.

| Biến mới ưu tiên | Fallback khi biến mới không tồn tại |
|---|---|
| DB_NAME | AZURE_POSTGRESQL_DATABASE |
| DB_USER | AZURE_POSTGRESQL_USERNAME |
| DB_PASSWORD | AZURE_POSTGRESQL_PASSWORD |
| DB_HOST | AZURE_POSTGRESQL_HOST |
| DB_PORT | AZURE_POSTGRESQL_PORT, rồi 5432 |

Giá trị mới rỗng vẫn có ưu tiên; PostgreSQL thiếu name/user/host báo lỗi rõ.
`DB_ENGINE=postgresql` chọn PostgreSQL; không đặt thì suy ra từ DB_HOST, không có
host thì SQLite. `DB_ENGINE=sqlite` ép SQLite kể cả còn biến Azure. Với SQLite,
DB_NAME là đường dẫn DB, mặc định BASE_DIR/db.sqlite3. Không còn host Azure cố định.
MEDIA_ROOT mặc định BASE_DIR/media, Compose ép `/app/media`.

Windows PowerShell chạy phát triển/test bằng venv đã cài requirements:

```powershell
$env:DEBUG="true"
$env:SECRET_KEY="test"
$env:DB_ENGINE="sqlite"
$env:DJANGO_ENV_FILE="NUL"
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test .
```

Nếu process còn DB_NAME từ PostgreSQL, xóa biến đó trước khi dùng SQLite.
`manage.py test` tự dùng StaticFilesStorage để checkout sạch không cần collectstatic;
mọi lệnh production vẫn dùng CompressedManifestStaticFilesStorage. Cách nhận diện
là `sys.argv[1:2] == ['test']`, không hỗ trợ runner nhúng gọi call_command('test')
với argv khác. Test manifest riêng chủ động override về storage production.

## 6. Sao lưu và khôi phục

Chạy các lệnh Bash này tại thư mục project. Đặt hệ thống vào bảo trì/dừng web để
DB và MEDIA thuộc cùng thời điểm; DB vẫn chạy. Thư mục backups cần bảo vệ quyền.

```bash
umask 077
mkdir -p backups
sudo docker compose stop nginx web
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' > backups/database.sql
sudo docker compose run --rm --no-deps --entrypoint tar web -C /app/media -czf - . > backups/media.tar.gz
sudo docker compose start web nginx
```

Kiểm tra file khác rỗng và thử restore trên môi trường tách biệt trước khi tin cậy
backup. Ví dụ khôi phục vào **DB trống mới** trên cùng service; các tên mới cần chưa
tồn tại. Không chạy trên DB thật nếu chưa có bản sao lưu và kế hoạch chuyển đổi:

```bash
sudo docker compose stop nginx web
sudo docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" inventory_restore'
sudo docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d inventory_restore' < backups/database.sql
sudo docker compose run --rm --no-deps --entrypoint tar web -C /app/media -xzf - < backups/media.tar.gz
```

Restore MEDIA ghi đè tệp trùng tên; nên thử trên volume mới và kiểm tra trước khi
chuyển môi trường thật. Sau khi xác minh, sửa DB_NAME trong `.env` thành
inventory_restore rồi `sudo docker compose up -d --wait`; không xóa DB cũ vội.
Quy trình backup/restore là hướng dẫn vận hành, chưa thực thi trên dữ liệu thật.

## 7. Cập nhật phiên bản và CI

Backup trước, ghi lại SHA hiện tại. Fetch fork, checkout SHA đã review rồi
`sudo docker compose up -d --build --wait --wait-timeout 180`, kiểm tra health/login
và nghiệp vụ. Entrypoint chạy migration. Rollback code không đảm bảo rollback
schema: khi không tương thích, khôi phục cả DB/MEDIA và image/SHA đã ghi.

Workflow `tests.yml` chỉ kiểm thử: Python 3.10/3.12 + PostgreSQL 16 và Docker Compose
smoke trên Ubuntu 24.04. Không cần collectstatic trong job test. Actions đã được bật
trên fork để chạy CI này; bốn workflow Azure/monitor cũ chỉ nhận workflow_dispatch,
không tự chạy khi push. Không dispatch chúng: vẫn chứa job Azure/monitor của tác giả.
Không có bước deploy hay mở PR trong workflow mới.
