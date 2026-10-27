# PRD: On-Demand Mobile Photo Crop & Rotate in Intake (`intake-photo-crop-rotate`)

## 1. Objective
Enable sourcing assistants and managers using `/intake/` on mobile phones (including narrow/low-DPI viewports like OPPO A74 `360×800` and `320×711`) to crop and rotate captured photos on-demand before AI pre-flight identification and form submission.

## 2. User Workflow & Requirements
1. **Non-Blocking Capture**:
   - Taking photos via camera or choosing from gallery continues to optimize images to `.webp` (`<= 2560px`) and display them immediately in the 2-column `#previewGrid`.
2. **Entry Points to Editor**:
   - Tapping the photo thumbnail itself, OR tapping a dedicated `✂️` edit button inside the thumbnail's bottom control pill opens `#imagePreviewModal` with the interactive crop & rotate editor active for that photo.
3. **Interactive Controls (Cropper.js v1.6.2)**:
   - **Freeform Touch Crop Box**: Initialized with `viewMode: 1`, `autoCropArea: 1` (100% bounds selected by default so rotating without cropping requires no handle dragging), `responsive: true`, `checkOrientation: false` (since `compressImageFile` already normalized EXIF orientation).
   - **90° Left / Right Rotation**: Tactile buttons `#rotateLeftBtn` (`↺ 90°`) and `#rotateRightBtn` (`↻ 90°`) calling `cropper.rotate(-90)` and `cropper.rotate(90)`.
   - **Save / Apply (`#applyCropBtn`)**: Renders `cropper.getCroppedCanvas({ maxWidth: 2560, maxHeight: 2560, imageSmoothingEnabled: true, imageSmoothingQuality: 'high' })`, encodes to `image/webp` (`0.82` quality, JPEG fallback), replaces `selectedFiles[currentLightboxIndex]`, calls `syncFileInput()` and `renderPreviews()`, and closes the modal (or updates in place).
4. **Offline / PWA & Low-Memory Safety**:
   - `cropper.min.js` and `cropper.min.css` (v1.6.2) are vendored locally under `inventory/static/inventory/vendor/`.
   - Any active `Cropper` instance and temporary `ObjectURL` are strictly destroyed when switching photos or closing `#imagePreviewModal`.
5. **Responsive & Accessibility Compliance**:
   - Zero horizontal overflow (`scrollWidth <= clientWidth`) at `320×711` and `360×800`.
   - Preserves existing modal ARIA landmarks (`role="dialog"`, `aria-modal="true"`, `aria-labelledby="modalPhotoTitle"`) and existing element IDs (`#modalPreviewImg`, `#modalPhotoCounter`, `#modalPrevBtn`, `#modalNextBtn`, `#closeImageModalBtn`).
