# Implementation Plan: Secondhand Inventory & Staging App

## Overview
A lightweight Django web application enabling a two-actor secondhand reselling workflow:
1. Field assistants snap photos and write quick raw notes from a mobile-friendly intake screen.
2. Managers use a central dashboard to inspect items, trigger Gemini Multimodal Vision AI to generate marketplace listing copy, download photos in a single `.zip` bundle, copy text to clipboard, and track sales status and Euro (`€`) prices.

All uploaded photos are postprocessed on the server with Pillow to auto-orient, compress, and store as `.webp` files.

---

## Architecture Decisions
- **Django App Structure:** Single focused app `inventory/` alongside project configuration `config/`.
- **Image Pipeline:** Dedicated `services/image_service.py` encapsulates Pillow operations. Images are transformed to WebP in-memory before saving to `media/products/%Y/%m/`.
- **AI Integration:** Dedicated `services/ai_service.py` using `google-genai` (Gemini Flash multimodal vision). Accepts image file pointers and raw notes, requests structured JSON response (`title`, `description`).
- **Archive Generation:** Standard library `zipfile` streams in-memory ZIP responses (`io.BytesIO`) directly to the browser for instant photo downloads.
- **Frontend Approach:** Django Templates styled with Tailwind CSS via CDN. Responsive mobile-first design for `/intake/` and desktop-optimized staging workflow for `/products/<pk>/`. Vanilla JavaScript for thumbnail previews and clipboard copy.
- **Permissions:** Built-in Django auth with two groups: `assistants` (intake & catalog view) and `managers` (AI trigger, pricing, status edits, downloads, admin).
- **Internationalization (i18n):** Django `LocaleMiddleware` with `Accept-Language` header detection, falling back to English (`en`). Manual language switcher via `set_language`. Windows-portable `.po` to `.mo` compilation using `polib`. Localized Gemini prompts matching UI language.
- **Cloud Asset Storage:** Oracle Cloud Infrastructure (OCI) Object Storage bucket replaces local disk storage via `django-storages[boto3]` using OCI's S3-compatible API endpoint with OCI Customer Secret Keys. Zero local disk footprint via in-memory WebP processing.

---

## Phases & Checkpoints

### Phase 1: Foundation & Domain Layer
- **Task 1:** Virtual Environment & Project Scaffolding
- **Task 2:** Domain Models (`Product`, `ProductImage`), Migrations & Admin
- **Task 3:** Pillow WebP Image Postprocessing Service & Unit Tests
- **Checkpoint 1 (Foundation):** Migrations apply cleanly, image service correctly validates and converts images to WebP, tests pass.

### Phase 2: Authentication & Assistant Intake (Vertical Slice 1)
- **Task 4:** Authentication & Role-Based Access Control
- **Task 5:** Mobile-First Product Intake Flow (Multi-upload, client preview, raw note saving)
- **Checkpoint 2 (Intake):** Assistant can log in, take/upload photos and notes, and images are saved on disk in WebP format.

### Phase 3: Manager Dashboard & Photo ZIP Bundle (Vertical Slice 2)
- **Task 6:** Manager Catalog Dashboard (Filters, search, product cards)
- **Task 7:** Product Detail Staging View & In-Memory ZIP Download
- **Checkpoint 3 (Catalog & Assets):** Manager can browse inventory, filter active/sold items, inspect staging page, and download the full `.webp` photo zip.

### Phase 4: Gemini Multimodal AI & Sales Tracking (Vertical Slice 3)
- **Task 8:** Gemini Multimodal Vision Service (`ai_service.py`)
- **Task 9:** AI Generation UI, One-Click Copy, and Sales Price / Sold Status Controls
- **Checkpoint 4 (Complete Flow):** Full end-to-end user journey works: intake -> dashboard -> AI generate -> copy copy -> download zip -> mark sold.

### Phase 5: Multi-Language (i18n) Support
- **Task 10:** Django i18n Configuration & Windows-Friendly PO/MO Compiler
- **Task 11:** UI Translation Coverage (Templates, Forms, Views, Navbar Switcher & Spanish PO/MO Catalog)
- **Task 12:** Localized Gemini AI Prompting & i18n Automated Tests
- **Checkpoint 5 (i18n Complete):** Bilingual UI verified with browser language detection, manual switcher, and localized AI outputs.

### Phase 6: Oracle Cloud Infrastructure Object Storage Integration
- **Task 13:** Dependency Installation & OCI Storage Backend Configuration (`django-storages[boto3]`)
- **Task 14:** In-Memory WebP Image Pipeline & Storage Decoupling (Zero local disk persistence)
- **Task 15:** Storage Integration Tests & Test Mocking
- **Checkpoint 6 (OCI Complete):** Product images upload to OCI bucket, local disk remains untouched, and all 51+ tests pass.

---

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Large mobile image uploads causing memory bloat | High | Enforce max 10 images / 10MB per file; process images sequentially in memory using Pillow. |
| Gemini API downtime or missing API key | Medium | Graceful error handling in `ai_service.py` with friendly user alerts; support manual editing fallback. |
| Mobile browser camera compatibility | Medium | Use standard HTML5 `<input type="file" accept="image/*" capture="environment" multiple>` for maximum compatibility. |
| EXIF orientation bugs on mobile uploads | Low | Use `PIL.ImageOps.exif_transpose` during WebP conversion to normalize orientation. |
| Missing GNU gettext tools on Windows | High | Provide Python-native `compile_locales` management command using `polib` to compile binary `.mo` files without external tools. |
| Tests failing due to missing OCI cloud credentials | High | Keep default storage configurable with in-memory / local fallback in test runner so CI/local tests remain fast and offline. |

---

## Open Questions / Notes
- None. (Approved: OCI S3-compatible API with Customer Secret Keys; Public read-only bucket/object visibility).

