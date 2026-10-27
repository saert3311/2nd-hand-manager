# Mobile Photo Crop & Rotate in Intake

## Problem Statement
How might we let sourcing assistants quickly rotate and freeform-crop captured photos on narrow mobile viewports (320px–360px OPPO A74) on-demand before upload—without slowing down rapid photo capture or exhausting mobile browser memory?

## Recommended Direction
Upgrade the existing `#imagePreviewModal` in `inventory/templates/inventory/intake.html` into an interactive Crop & Rotate workspace powered by locally vendored **Cropper.js v1.6.2** (`inventory/static/inventory/vendor/cropper.min.js` & `cropper.min.css`).

Photos captured via camera or gallery continue to flow directly through client-side WebP optimization (`2560px`) into the 2-column `#previewGrid`. Tapping any photo thumbnail (or a dedicated `✂️` edit button in the thumbnail control bar) opens the modal with:
1. A freeform touch crop box (`viewMode: 1`, `dragMode: 'move'`, `autoCropArea: 1` so the full image is selected by default if the user only wants to rotate).
2. Two tactile rotation buttons (`↺ 90°` and `↻ 90°`).
3. A primary **Apply (`✓ Aplicar`)** button that renders the cropped/rotated canvas (`maxWidth: 2560, maxHeight: 2560`), encodes it as a `.webp` `File` (`0.82` quality), replaces `selectedFiles[idx]` in place, syncs the `<input type="file">`, and refreshes the thumbnail preview.

## Key Assumptions to Validate
- [x] Setting `autoCropArea: 1` (100% initial crop box) lets users do a quick 90° rotate + Apply in 2 taps without unintentionally cropping edges.
- [x] All modal controls (`◀`, `▶`, `↺`, `↻`, `Cancel`, `Apply`) fit cleanly on a `320×711` (zoomed OPPO A74) viewport with zero horizontal overflow (`scrollWidth <= clientWidth`).
- [x] Destroying the `Cropper` instance on modal close prevents memory growth across repeated edits.

## MVP Scope
- **In**:
  - Vendor `cropper.min.js` and `cropper.min.css` under `inventory/static/inventory/vendor/`.
  - Add a `✂️` edit trigger button on each 2-column thumbnail card (in addition to tapping the thumbnail image itself).
  - Interactive freeform crop box + `↺ 90°` / `↻ 90°` buttons inside `#imagePreviewModal`.
  - In-place WebP `File` replacement in `selectedFiles[idx]` + `syncFileInput()`.
  - Bilingual (`en` / `es`) labels and Playwright/Django test verification across `320×711` and `360×800`.

## Not Doing (and Why)
- **No mandatory pre-upload modal intercept**: Slows down batch intake when photos don't need editing.
- **No aspect-ratio preset pills (`1:1`, `4:3`, `16:9`)**: Adds toolbar clutter on 320px screens; freeform crop handles any product shape.
- **No multi-version undo history / original file cache**: Doubles in-memory Blob footprint on low-RAM Android phones.
- **No brightness/contrast/filter sliders**: Unnecessary for secondhand staging and can distort true item condition.
