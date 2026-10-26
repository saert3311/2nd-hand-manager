# Idea: Detail View Photo Upload Component System

## Context & Motivation
In Phase 33, we introduced direct photo uploads on the Product Detail workspace (`/products/<pk>/`), allowing managers to snap or attach photos post-intake. However, the initial implementation used a basic HTML `<input type="file">` selector.

In our Intake workspace (`/intake/`), we already engineered a state-of-the-art, mobile-first photo upload component system featuring:
1. **Dashed Dropzone & Drag-and-Drop**: Desktop drag & drop support with hover/dragover highlights.
2. **Dual Mobile Capture Triggers**: Dedicated "📸 Tomar foto" (direct camera trigger with `capture="environment"`) and "🖼️ Seleccionar de la galería" (multi-file gallery picker).
3. **Client-Side Canvas Optimization**: Fast WebP downscaling to 2560px (quality 0.82) with hardware EXIF orientation handling, preventing Android Low Memory Killer (LMK) browser tab crashes and saving 85%+ upload bandwidth.
4. **Interactive Previews Before Submission**: Visual thumbnail preview grid with index badges, slot availability counter, and individual remove actions.
5. **Real-Time Compression Feedback**: Inline accessible progress spinner and status messages during client-side compression.

## The Idea
Bring the exact same rich, responsive photo upload component system from Intake into the Product Detail view.

Managers should enjoy the exact same high-polish experience:
- Tap "Tomar foto" on mobile to snap tag/measurement photos directly.
- Drag & drop photos directly into the gallery section on desktop.
- See immediate thumbnails and remove mistakes before uploading.
- Have files auto-compressed to WebP 2560px client-side before sending over the wire.
- Never crash Android mobile browsers when uploading multi-megapixel smartphone photos.
- Respect the product's remaining photo capacity (up to 10 total).
