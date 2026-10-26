# PRD: Low-DPI Intake Photo Miniatures & Delete Controls Optimization

## 1. Executive Summary & Problem Statement

In the mobile-first warehouse intake workflow (`/intake/`), sourcing assistants use a variety of handheld mobile devices, including dedicated rugged barcode scanners (Honeywell Dolphin, Zebra TC-series) and budget Android smartphones. These devices frequently feature **low-DPI displays** (1x device pixel ratio, ~160–240 dpi) and compact viewport widths (320px–390px).

### Observed Failure Modes on Low-DPI & Compact Devices:
1. **Oversized Thumbnails ("Miniatures Appear Too Big")**:
   - The preview grid used `grid-cols-2`, creating giant cards (~160px–180px square).
   - A typical intake session of 6 photos created 3 tall rows consuming >480px of vertical height, pushing the AI pre-flight identification button, notes textarea, and save button completely off-screen.
2. **Ambiguous & Obscured Delete ('X') Controls**:
   - The delete button floated arbitrarily over the top-right corner with a semi-transparent circular badge. On busy or light-colored photo backgrounds, the thin SVG cross suffered from subpixel aliasing on 1x DPI displays, making it hard to see and discern whether it was a delete action or an image artifact.
3. **Severe Photo Surface Occlusion**:
   - Top badges (`⭐ #1 Cover` or `#N`) and bottom reorder controls (`◀`, `⭐ Cover`, `▶`) spanned across the top and bottom of each thumbnail. Combined with `object-cover` square cropping, more than 50% of the visible image was occluded or cropped out, preventing assistants from recognizing which angle or garment detail was depicted.
4. **Lack of Inspection / Zoom Capability**:
   - Assistants had no way to verify whether a captured photo was blurry, if serial numbers or care tags were legible, or if lighting was adequate before submitting to Gemini AI.

---

## 2. Objectives & Success Criteria

1. **Compact, High-Density Miniature Grid**:
   - Standardize on a responsive 3-column mobile layout (`grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 sm:gap-2.5`).
   - Thumbnails render at ~90px–115px square on 320px–390px viewports, displaying up to 6–9 photos in a compact, scannable gallery view without displacing core intake form controls.
2. **Unambiguous, High-Contrast Delete ('X') Button**:
   - Render a high-contrast circular badge (`bg-rose-600 hover:bg-rose-700 text-white`) with a bold, crisp cross icon (`stroke-width="3"`), encased in a subtle white contrast ring (`ring-1 ring-white/90`) to guarantee instant legibility against any image background on 1x DPI screens.
   - Maintain an accessible tap target (minimum 32×32px / 36×36px) positioned at `top-1 right-1`.
3. **Streamlined, Non-Obstructive Badges & Controls**:
   - Compact top-left position badges (`⭐ 1` for cover, `#2`, `#3` for sequence) that leave ample breathing room for the image.
   - Compact, semi-transparent dark floating control pill (`bg-slate-900/80 backdrop-blur-xs`) for `◀`, `⭐`, `▶` reordering controls, preserving over 70% of the thumbnail surface.
4. **Full-Size Photo Inspection Lightbox Modal**:
   - Tapping on any thumbnail opens an accessible inspection modal (`role="dialog"`, `aria-modal="true"`) displaying the uncropped image (`object-contain max-h-[85vh]`), sequence title ("Foto 1 de 4"), and dismiss button (`Escape` key, backdrop click, or close button).
5. **Zero Regressions**:
   - Preserve all existing capabilities: `selectedFiles` state, `syncFileInput()` `DataTransfer` synchronization, desktop drag-and-drop, pre-flight AI identification gate (`hasIdentified`), and bilingual Spanish/English localization.

---

## 3. Architecture & Functional Requirements

### 3.1. Grid Density & Card Structure (`inventory/templates/inventory/intake.html`)
- **Container**:
  ```html
  <div id="previewGrid" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 sm:gap-2.5"></div>
  ```
- **Thumbnail Card**:
  - `relative aspect-square rounded-xl overflow-hidden border border-slate-200/90 shadow-xs bg-slate-900 group transition-all duration-150`
  - Encapsulates:
    1. `<img>` with `object-cover w-full h-full cursor-pointer hover:opacity-95 transition`.
    2. Top-left sequence/cover badge.
    3. Top-right high-contrast delete button.
    4. Bottom compact floating reorder pill.

### 3.2. Delete ('X') Button Specification
- **Visual Design**:
  - `visualBadge`: `w-6 h-6 rounded-full bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white flex items-center justify-center shadow-md ring-1 ring-white/90 transition-transform active:scale-90`.
  - Icon: SVG cross with `stroke-width="3"` (`viewBox="0 0 24 24"`) ensuring crisp pixel alignment on 1x DPI screens.
- **Accessibility**:
  - `delBtn.setAttribute('aria-label', '{% trans "Remove photo" %} #' + (idx + 1))`.
  - Dedicated tap area that prevents misclicks on adjacent reorder controls.

### 3.3. Tap-to-Inspect Lightbox Modal (`#imagePreviewModal`)
- **DOM Container**:
  - Semantic modal dialog overlay appended to `/intake/`.
  - Backdrop: `fixed inset-0 bg-slate-950/85 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-4`.
  - Card: `max-w-2xl w-full bg-slate-900 rounded-2xl shadow-2xl border border-slate-700/80 overflow-hidden flex flex-col`.
  - Image: `w-full max-h-[75vh] sm:max-h-[80vh] object-contain bg-black/40 select-none`.
  - Footer/Header: Displays photo index, cover badge status, and clear "Cerrar" / "Close" action button.
- **Interaction**:
  - Tapping a thumbnail triggers `openLightbox(idx)`.
  - Dismissible via "Cerrar" button, clicking outside the image card, or pressing `Escape`.

---

## 4. Bilingual Localization & Accessibility (`a11y`)

1. **Localization**: All UI labels, modal controls, and button tooltips wrapped in `{% trans %}` and translated into Spanish (`locale/es/LC_MESSAGES/django.po`):
   - "Foto {x} de {total}" / "Photo {x} of {total}"
   - "Cerrar vista previa" / "Close preview"
   - "Toca para ampliar foto" / "Tap to enlarge photo"
2. **WCAG Compliance**:
   - Contrast ratio of delete button white cross against rose-600 background exceeds 4.5:1.
   - Focus rings on keyboard navigation (`focus:ring-2 focus:ring-rose-500`).
   - Modal traps focus appropriately with ARIA role semantics.
