# Product Requirements Document (PRD): Oracle Cloud Infrastructure (OCI) Object Storage Integration

## 1. Executive Summary
Migrate all product image storage from local filesystem disk (`media/products/`) to Oracle Cloud Infrastructure (OCI) Object Storage. All uploaded product images will be processed in-memory to WebP format and saved directly to a dedicated OCI Object Storage bucket. No images will be permanently stored on the local application server filesystem.

---

## 2. Problem Statement
The current implementation writes WebP product images directly to `MEDIA_ROOT` on the local server disk. This presents several constraints:
- **Disk Consumption:** High-volume secondhand cataloging quickly exhausts local VM/container storage.
- **Stateless & Scalable Deployment:** Modern containerized/cloud platforms require decoupled, stateless application servers where file storage persists independently of container restarts or multi-instance scaling.
- **Centralized Asset Management:** Assets should be securely and durably persisted in enterprise cloud storage with lifecycle management and configurable access control.

---

## 3. User Personas & Scenarios

### Persona 1: Field Sourcing Assistant
- **Scenario:** Assistant uploads up to 10 photos of an incoming secondhand item on `/intake/`.
- **Expectation:** Images are converted to WebP in memory and transferred directly into the OCI Object Storage bucket. The assistant experiences immediate upload feedback with zero local disk footprint.

### Persona 2: Manager / Lister
- **Scenario 1 (Browsing):** Views catalog dashboard and product staging detail. Thumbnail images and full gallery photos load seamlessly from OCI storage URLs.
- **Scenario 2 (Asset Bundle):** Clicks "Download Photos (.ZIP)". The server streams image bytes from OCI Object Storage into an in-memory zip archive and streams it to the user.
- **Scenario 3 (AI Listing Generation):** Clicks "Generate AI Listing". The backend fetches image bytes from OCI storage and delivers them to Google Gemini Flash Multimodal Vision.

---

## 4. Scope & Functional Requirements

### 4.1 Storage Architecture
- **Target Backend:** Oracle Cloud Infrastructure Object Storage bucket.
- **Django Storage Integration:** Implement or configure a dedicated Django storage backend so Django `ImageField` (`ProductImage.image`) transparently saves, retrieves, and builds URLs for OCI Object Storage.
- **Zero Local Disk Footprint:** All image transformations (Pillow orientation correction and WebP conversion) occur in-memory using `io.BytesIO` / `ContentFile`. No image files are written to local disk.
- **Object Path Convention:** `products/%Y/%m/product_<hash>.webp`.

### 4.2 Credential & Connection Configuration
- Support standard OCI configuration options via environment variables (`.env`):
  - **Option A (OCI S3-Compatible API):** Using OCI Customer Secret Keys (`OCI_STORAGE_ACCESS_KEY`, `OCI_STORAGE_SECRET_KEY`, `OCI_STORAGE_BUCKET_NAME`, `OCI_STORAGE_NAMESPACE`, `OCI_STORAGE_REGION`, `OCI_STORAGE_ENDPOINT_URL`).
  - **Option B (Native OCI SDK):** Using OCI API Key configuration (`OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_PRIVATE_KEY_PATH` or `OCI_KEY_CONTENT`, `OCI_STORAGE_BUCKET_NAME`, `OCI_STORAGE_NAMESPACE`, `OCI_STORAGE_REGION`).
- Graceful validation: Clear error messaging when storage credentials are unset or invalid.

### 4.3 Staging Workflow Compatibility
- **Image Serving:** `ProductImage.image.url` returns the accessible OCI URL.
- **ZIP Packaging:** `product_download_zip_view` streams file contents from storage (`img_obj.image.open('rb')`) into the in-memory ZIP buffer without requiring local file path access.
- **Gemini AI Service:** `generate_product_listing` reads image bytes from the storage abstraction without assuming files exist on local disk.

### 4.4 Testability & Local Development Fallback
- Automated test suites (`python manage.py test`) must run deterministically in CI and local developer machines without requiring live OCI network connections or real cloud credentials.
- Unit and integration tests will use mocked storage or a test storage adapter to verify OCI operations in isolation.

---

## 5. Non-Functional Requirements
- **Durability & Security:** Zero credential leakage in source code; all access tokens and keys loaded from `.env`.
- **Performance:** In-memory image processing ensures no redundant disk I/O latency before uploading to OCI.
- **Portability:** Compatible with Windows and Linux execution environments.

---

## 6. Success Metrics
- 100% of newly uploaded product images persist in the OCI Object Storage bucket.
- Zero product image files written to local disk (`media/products/` remains empty).
- Photo gallery displays images correctly via OCI URLs.
- ZIP photo download packages OCI-backed images correctly.
- Gemini Multimodal Vision receives image bytes fetched from OCI storage.
- All existing tests (51+) and new OCI storage integration tests pass cleanly.
