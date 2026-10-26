# PRD: Detail View Photo Upload Component System (Phase 34)

## 1. Executive Summary & Objective

In second-hand operations, product details and photo documentation continuously evolve after initial intake. Store managers frequently need to add supplemental photos—such as close-ups of fabric composition tags, care labels, wear marks, measurements, or alternative styling angles requested by prospective marketplace buyers.

While Phase 33 enabled manager-level photo uploads in the Product Detail workspace (`/products/<pk>/`), the UI was limited to a rudimentary, browser-native `<input type="file">` selector. This lacked the modern ergonomics, mobile responsiveness, and client-side performance protections established in the Intake flow (`/intake/`).

### Primary Objectives:
1. **Unify Photo Upload Component Experience**: Implement the rich, mobile-first photo upload component system from Intake directly within the Product Detail workspace (`/products/<pk>/`).
2. **Dual Capture Ergonomics**: Provide explicit, accessible dual action buttons:
   - **📸 Take Photo** (`#detailCameraInput` with `accept="image/*" capture="environment"`): Direct rear-camera trigger for rapid mobile shooting.
   - **🖼️ Choose from Gallery** (`#detailImageInput` with `accept="image/*" multiple`): System gallery/file explorer multi-file selection.
3. **Interactive Dropzone with Drag & Drop**: A dashed drag-and-drop zone (`#detailDropZone`) with visual hover/dragover highlights for desktop workflows.
4. **Client-Side WebP Compression & Memory Protection**: Utilize in-browser Canvas downscaling to max 2560px WebP (quality 0.82) with EXIF orientation correction, preventing Android Low Memory Killer (LMK) browser crashes and drastically speeding up uploads.
5. **Pre-Upload Thumbnail Queue & Removal**: Render an interactive pending-upload preview grid (`#detailPendingPreviewGrid`) with individual photo removal buttons (✕) before submitting.
6. **Capacity-Aware Counter & Limits**: Dynamically compute remaining photo slots ($10 - N_{existing}$), display a live counter (`X / Y available`), and gracefully guard against exceeding the 10-photo ceiling.
7. **Maintain Platform Sync Invariants**: Submitting additional photos on published products continues to flag `needs_platform_sync = True` seamlessly.

---

## 2. User Stories & Core Use Cases

### User Story 1: Snapping a Tag Photo via Smartphone Camera
*As a store manager inspecting an incoming vintage leather jacket on my smartphone in the product detail view, a Wallapop buyer asks for a close-up of the YKK zipper and leather label. I tap the high-contrast "📸 Tomar foto" button, which immediately triggers the smartphone's camera without bubbling or opening the gallery. I snap the photo, see the thumbnail appear in the pending queue with a compression indicator, and tap "Subir fotos seleccionadas". The photo is uploaded, converted to WebP, and appended to the product gallery.*

### User Story 2: Desktop Drag & Drop Batch Upload
*As a store manager working on my desktop computer with DSLR product photos in my file manager, I drag 3 image files and drop them onto the dashed `#detailDropZone` in the product detail view. The dropzone highlights in emerald green on dragover. Once dropped, client-side Canvas processes the files into WebP, displays 3 thumbnails with badges in the pending preview grid, and updates the counter to "3 fotos seleccionadas (quedan 2 disponibles)". I click "Subir fotos seleccionadas" to save them.*

### User Story 3: Removing a Mistakenly Selected Photo Before Uploading
*As a store manager selecting 4 photos from my phone gallery, I accidentally choose an unrelated personal photo. In the pending thumbnail preview grid, I tap the red "✕" button on that specific thumbnail. The thumbnail is instantly removed from the pending list and the HTML file input without having to restart the selection process.*

### User Story 4: Capacity Ceiling Enforcement
*As a store manager viewing a product with 8 existing photos, the component clearly indicates "Quedan 2 disponibles (máximo 10)". When I attempt to select 4 photos, the system displays an accessible notice: "Solo puedes añadir hasta 2 fotos más", adds the first 2 photos to the pending queue, and ignores the excess.*

---

## 3. Technical Architecture & Functional Requirements

### 3.1. Frontend Component Structure (`inventory/templates/inventory/product_detail.html`)

When `can_manage = True` and `product.images.count < 10`:

```html
<!-- Enhanced Add More Photos Component -->
<div id="detailPhotoUploadContainer" class="pt-4 border-t border-slate-100 space-y-3">
  <div class="flex items-center justify-between">
    <label class="text-xs sm:text-sm font-bold text-slate-700 uppercase tracking-wider">
      {% trans "Add More Photos" %}
    </label>
    <span id="detailUploadSlotCount" class="text-xs font-semibold text-slate-500">
      {% blocktrans with available=available_slots count=product.images.count %}
        {{ available }} available ({{ count }}/10)
      {% endblocktrans %}
    </span>
  </div>

  <!-- Interactive Dashed Dropzone -->
  <div id="detailDropZone" class="border-2 border-dashed border-slate-300 hover:border-emerald-500 rounded-2xl p-4 sm:p-5 text-center bg-slate-50 hover:bg-emerald-50/40 transition cursor-pointer relative group">
    <input type="file" name="images" id="detailImageInput" multiple accept="image/*" class="sr-only">
    <input type="file" id="detailCameraInput" accept="image/*" capture="environment" class="sr-only">
    
    <div class="space-y-2.5">
      <div class="w-10 h-10 mx-auto rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl group-hover:scale-105 transition duration-150">
        📷
      </div>
      <div>
        <p class="text-sm sm:text-base font-bold text-slate-800">{% trans "Tap to take photos or upload" %}</p>
        <p class="text-xs text-slate-500 mt-0.5">{% trans "Select up to available slots (auto-optimized to WebP 2560px)" %}</p>
      </div>

      <!-- Dual Action Triggers -->
      <div class="flex flex-wrap items-center justify-center gap-2 pt-1">
        <label for="detailCameraInput" id="btnTriggerDetailCamera" role="button" tabindex="0"
               class="inline-flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-bold rounded-xl shadow-sm text-xs sm:text-sm transition cursor-pointer min-h-[38px] select-none">
          <span class="text-base leading-none">📸</span>
          <span>{% trans "Take Photo" %}</span>
        </label>
        <label for="detailImageInput" id="btnTriggerDetailGallery" role="button" tabindex="0"
               class="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-100 active:bg-slate-200 text-slate-700 font-bold rounded-xl border border-slate-300 shadow-sm text-xs sm:text-sm transition cursor-pointer min-h-[38px] select-none">
          <span class="text-base leading-none">🖼️</span>
          <span>{% trans "Choose from Gallery" %}</span>
        </label>
      </div>
    </div>
  </div>

  <!-- Inline Compression Indicator -->
  <div id="detailCompressionIndicator" role="status" aria-live="polite" class="hidden ...">
    ...
  </div>

  <!-- Pending Thumbnails Preview Grid -->
  <div id="detailPendingContainer" class="hidden space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-xs font-bold text-slate-600 uppercase tracking-wider">
        {% trans "Photos Ready to Upload:" %}
      </p>
      <button type="button" id="btnClearDetailPending" class="text-xs text-rose-600 hover:text-rose-800 font-medium">
        {% trans "Clear All" %}
      </button>
    </div>
    <div id="detailPendingGrid" class="grid grid-cols-4 sm:grid-cols-5 gap-2"></div>
  </div>

  <!-- Submit Form -->
  <form id="detailUploadForm" method="post" action="{% url 'inventory:product_upload_images' product.pk %}" enctype="multipart/form-data">
    {% csrf_token %}
    <input type="file" name="images" id="detailFormImages" multiple class="hidden">
    <button type="submit" id="btnUploadDetailPhotos" disabled class="...">
      <span>⬆️</span> {% trans "Upload Selected Photos" %}
    </button>
  </form>
</div>
```

---

### 3.2. Client-Side Script Engine (`product_detail.html`)

1. **State Tracking**:
   - `existingCount`: Number of already uploaded images attached to the product.
   - `maxAvailable = 10 - existingCount`.
   - `pendingFiles = []`: Array of optimized `File` objects waiting to be uploaded.
2. **`compressImageFile(file, maxDimension, quality)`**:
   - Same battle-tested routine from `intake.html`: EXIF orientation via `createImageBitmap` with fallback to `Image()`.
   - Canvas downscaling to max 2560px on longest dimension.
   - Export to `image/webp` (0.82) with fallback to `image/jpeg`.
3. **`handleIncomingFiles(filesList)`**:
   - Sequential optimization with status updates on `#detailCompressionIndicator`.
   - 10MB individual file size validation.
   - Exact duplicate filter (`name` + `size`).
   - Slot truncation to `maxAvailable - pendingFiles.length`.
   - Populates `pendingFiles`, triggers `syncFormFileInput()`, and renders `#detailPendingGrid`.
4. **Touch & Click Event Isolation**:
   - Direct `e.stopPropagation()` on `#detailCameraInput` and `#detailImageInput` click listeners to prevent click bubbling up to `#detailDropZone` (avoiding unintended secondary file dialogs on Android/iOS).
   - `#btnTriggerDetailCamera` explicitly triggers `#detailCameraInput.click()`.
   - Direct click on `#detailDropZone` background triggers `#detailImageInput.click()`.
5. **Form Synchronization**:
   - `DataTransfer` object sets `detailFormImages.files = dt.files`.
   - Enables `#btnUploadDetailPhotos` when `pendingFiles.length > 0`, disables when 0.

---

### 3.3. Backend View Validation (`inventory/views.py`)
- `product_upload_images_view` remains authoritative:
  - Validates `current_count + len(files) <= 10`.
  - Uses `convert_to_webp()` in memory via `image_service.py` as defense-in-depth against malicious file uploads.
  - Automatically flags `needs_platform_sync = True` if the product is published.
  - Returns redirect to `/products/<pk>/` with flash success/error messages.

---

## 4. Invariants & Rules

1. **Strict 10-Photo Invariant**: Total attached photos for any single product can never exceed 10 across frontend and backend.
2. **Defense-in-Depth Optimization**: Photos are compressed client-side to WebP 2560px for bandwidth/memory performance, AND validated/sanitized server-side by Pillow.
3. **Published Synchronization Rule**: Uploading photos to an already published item MUST trigger `needs_platform_sync = True`.
4. **Zero Layout Regressions**: Existing photo gallery, cover reordering, full-size modal viewer, and thumbnail deletion remain completely functional and compatible.
5. **Localization Guarantee**: 100% of new user-facing strings must be localized in Spanish (`locale/es/LC_MESSAGES/django.po`) and English.

---

## 5. Non-Goals
- Changing the max photo limit from 10 to a different number.
- Replacing the server-side image processing backend.
- Modifying the Intake view (`/intake/`).
