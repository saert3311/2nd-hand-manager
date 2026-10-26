# PRD: Photo Reordering in Intake and Detail Workspaces

## 1. Executive Summary & Objective

In second-hand goods cataloging and marketplace staging (Wallapop, Vinted, eBay, Milanuncios), the **order of product photos** is critical to sales conversion and AI vision analysis:
- The **first photo (`order = 0`)** serves as the **Primary Cover Photo** (`product.primary_image`) shown across catalog dashboards, thumbnail cards, and marketplace listings.
- In pre-flight AI vision identification and listing copywriting, the first 3 photos are prioritized by Gemini Vision for brand tagging, condition detection, and valuation benchmarks.

Currently, photos can only be added or deleted; users cannot reorder photos during intake or after staging. This PRD defines an intuitive, mobile-first, accessible photo reordering feature across both the **Intake Form** (`/intake/`) and the **Product Detail Workspace** (`/products/<pk>/`).

---

## 2. User Stories & Core Use Cases

1. **Intake Assistant Photo Ordering**:
   *As a sourcing assistant at the warehouse intake station, after capturing or uploading 4 photos on my smartphone, I want to quickly set the best shot (e.g., full front view) as the cover photo (#1) before saving, so the catalog displays an attractive thumbnail without having to delete and re-shoot.*
2. **Intake Touchscreen & Desktop Ergonomics**:
   *As an assistant on mobile, I want one-tap reorder controls ("Move Left", "Move Right", and 1-click "Set as Cover") that never misfire or conflict with vertical scrolling, while also having smooth drag-and-drop on desktop.*
3. **Manager Detail Staging Reordering**:
   *As a store manager refining a product listing on the desktop dashboard, I want to reorder existing product photos, elevate a detail shot or clean cover to the primary position, and have the changes persist immediately in the database and update the featured image preview.*

---

## 3. Architecture & Functional Requirements

### 3.1. Intake Form Reordering (`inventory/templates/inventory/intake.html`)
- **State Management**: Manipulates the in-memory `selectedFiles` array (`File[]`).
- **Hybrid Interaction Pattern**:
  - **Click/Tap Buttons on Preview Cards**:
    - `◀` Move Left (disabled on first item, index 0).
    - `▶` Move Right (disabled on last item, index N-1).
    - `⭐ Portada / Cover` button (displayed on items with index > 0; moves photo to index 0).
    - `✕` Remove Photo button (existing functionality preserved).
  - **HTML5 Drag-and-Drop**:
    - Thumbnail cards have `draggable="true"` and desktop drag-and-drop handles (`dragstart`, `dragover`, `dragleave`, `drop`, `dragend`) with clear drop-target visual indicators.
- **Badge Indicators**:
  - Index 0 displays a distinctive primary cover badge: `⭐ #1 Portada` / `⭐ #1 Cover`.
  - Indices 1..N display `#2`, `#3`, etc.
- **Form & Hardware Synchronization**:
  - Any reordering immediately calls `syncFileInput()`, constructing a new `DataTransfer` object and updating `imageInput.files`.
  - When the form is submitted, `request.FILES.getlist('images')` arrives in the reordered sequence, assigning `order = 0, 1, 2...` to `ProductImage` objects in `inventory/views.py`.
- **Pre-flight AI Identification Gate**:
  - Reordering photos **preserves** the identification gate status (`hasIdentified`) if AI identification was already run.
  - If pre-flight AI identification is re-triggered, it automatically slices the newly ordered first 3 photos (`selectedFiles.slice(0, 3)`).

### 3.2. Product Detail Form Reordering (`inventory/templates/inventory/product_detail.html` & `inventory/views.py`)
- **Permission Boundary**:
  - Restricted to Store Managers (`can_manage=True` / `@manager_required`). Sourcing assistants have a read-only view of the gallery.
- **Interactive Gallery Reordering**:
  - Inside the "Photo Gallery Card", managers have an intuitive "Reorganize Photos" toggle or inline controls on each thumbnail.
  - Each thumbnail displays its position `#1 (Cover)`, `#2`, etc.
  - Each thumbnail provides:
    - `◀` Move Left and `▶` Move Right controls.
    - `⭐ Set as Cover` (moves item to #1).
    - Drag-and-drop reordering.
- **Backend API Endpoint**:
  - **Route**: `POST /products/<pk>/images/reorder/` (`name="product_reorder_images"`)
  - **Access Control**: `@login_required`, `@manager_required`, `@require_POST`.
  - **Validation**:
    - Validates JSON payload `{ "image_ids": [id1, id2, ...] }`.
    - Confirms all `image_ids` belong to `product.images`.
    - Enforces length match with `product.images.count()`.
  - **Database Persistence**:
    - Updates `ProductImage.order = index` inside `transaction.atomic()`.
    - Preserves `ProductImage.image` binary and metadata.
  - **Response**: `{ "success": True, "reordered_ids": [...] }`.
- **Live DOM Synchronization**:
  - On successful response:
    - `#mainImage` updates to the new primary image (`product.primary_image`).
    - The thumbnail strip visually reflects the new order with active cover badge.
    - Displays an accessible confirmation toast / notice (*"Orden de fotos guardado"* / *"Photo order saved"*).
  - On network/server failure:
    - Reverts DOM order to prior state and displays an accessible alert banner.

---

## 4. Accessibility & Mobile Standards (`frontend-ui-engineering`)

1. **Touch Target Size**: All reorder and cover buttons have minimum touch targets of 36×36px on mobile viewports.
2. **Keyboard Accessibility**: All buttons are focusable via `Tab` with visible focus rings (`focus:ring-2 focus:ring-emerald-500`) and operable via `Enter` / `Space`.
3. **Screen Reader Feedback**: Dynamic announcements using `aria-live="polite"` when a photo is moved or promoted to cover (e.g., *"Photo 2 moved to cover"* / *"Foto 2 convertida en portada"*).
4. **No Gesture Conflict**: Tap controls ensure users on iOS Safari and Android never suffer from drag-and-drop gesture collisions with vertical scrolling.

---

## 5. Non-Functional Requirements & Security

1. **Atomic Updates**: Database reordering executes in a single database transaction (`transaction.atomic()`).
2. **CSRF Protection**: All POST requests include `X-CSRFToken`.
3. **Foreign Key Integrity**: Reordering endpoint rejects any ID not belonging to the specific `Product`.
4. **Zero-Failure Gate**: 100% test pass rate across unit, view, permission, and regression suites.
