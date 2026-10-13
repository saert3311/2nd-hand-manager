# 2ndHand Staging Hub 📦

A high-efficiency staging, cataloging, and marketplace listing hub for secondhand clothing and vintage goods resellers. Integrates mobile rapid intake, Gemini Multimodal Vision AI, and marketplace link tracking (Wallapop, Vinted, eBay, Milanuncios).

---

## 🚀 Quickstart with Docker

The easiest way to run the application is with Docker and Docker Compose.

### 1. Prerequisites
- Docker Engine 24+ and Docker Compose v2+

### 2. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` and add your `GEMINI_API_KEY` (required for AI listing generation).

### 3. Start the Application
Run in standalone mode (uses persistent SQLite volume and WhiteNoise static asset serving):
```bash
docker compose up --build -d
```
The application will automatically:
- Execute all pending database migrations
- Collect and compress static assets
- Launch Gunicorn with 3 workers on port 8000

Access the web interface at: **[http://localhost:8000](http://localhost:8000)**

### 4. Running with PostgreSQL (Optional)
To run with a dedicated PostgreSQL database container instead of SQLite:
```bash
docker compose --profile postgres up --build -d
```

### 5. Inspect Logs & Stop
View live logs:
```bash
docker compose logs -f web
```
Stop containers:
```bash
docker compose down
```

---

## 🛠️ Local Development (Without Docker)

### 1. Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Database Migrations
```bash
python manage.py migrate
```

### 3. Create Superuser (Manager)
```bash
python manage.py createsuperuser
```

### 4. Seed Marketplace Sites & Sample Inventory (Optional)
```bash
python seed_products.py
```

### 5. Start Development Server
```bash
python manage.py runserver
```

---

## 🧪 Testing & CI/CD Quality Gates

This project enforces strict **Shift-Left** quality gates defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. **Lint & Style Check**: `ruff check .`
2. **System Health Check**: `python manage.py check`
3. **Automated Test Suite**: `python manage.py test` (162 tests covering permissions, security, and image processing)
4. **Docker Image Build**: Multi-layer build cached with GitHub Actions GHA cache
5. **Non-Root User Enforcement**: Asserts container runs with unprivileged UID 10001
6. **Container Smoke Test**: Boots container in CI, asserts healthy status, and verifies page response

To run checks locally before pushing:
```bash
ruff check .
python manage.py test
```

---

## 🌐 Automated Remote Deployment (GHCR + Watchtower)

Deploy continuously on any remote VPS without building images on the server:

### 1. Automated Image Build & Publish
When changes merge into `master`, GitHub Actions automatically:
- Executes all 6 quality gates and tests.
- Builds the production image with Python 3.13 slim.
- Publishes the image to **GitHub Container Registry**: `ghcr.io/saert3311/2nd-hand-manager:latest`.

### 2. On Your Remote Server (One-Time Setup)
1. Transfer or clone `docker-compose.prod.yml` and `.env` onto your server:
   ```bash
   mkdir -p /opt/secondhand && cd /opt/secondhand
   curl -O https://raw.githubusercontent.com/saert3311/2nd-hand-manager/master/docker-compose.prod.yml
   cp .env.example .env
   nano .env  # set SECRET_KEY, DEBUG=False, ALLOWED_HOSTS=yourdomain.com, GEMINI_API_KEY
   ```
2. Start the production stack:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

### 3. Hands-Free Automated Updates
The included **Watchtower** service monitors `ghcr.io/saert3311/2nd-hand-manager:latest`:
- When GitHub Actions pushes a new version, Watchtower automatically downloads the new image, gracefully restarts the web container, preserves all volumes, and deletes old images.
- No SSH keys or webhook ports needed on the server!

---

## 🔒 Security & Architecture Highlights

- **Non-Root Execution**: Runs under unprivileged `appuser:appgroup` (UID 10001).
- **Safe Static Serving**: WhiteNoise compresses and serves static files with cache-busting headers.
- **Decompression Bomb & Polyglot Protection**: Uploaded images are re-encoded into WebP in memory, neutralizing EXIF injection and pixel flood attacks.
- **URL Scheme Validation**: Only `http://` and `https://` schemes permitted across marketplace links.
- **Decoupled Storage**: Seamlessly switches between local filesystem mounts and Oracle Cloud Infrastructure (OCI) S3-compatible Object Storage via environment configuration.

