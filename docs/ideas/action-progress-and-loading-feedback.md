# Idea One-Pager: Action Progress & Non-Blocking Loading Feedback

**Problem:** Across the staging workflow (`/intake/` and `/products/<pk>/`), long-running AI requests (Gemini photo identification, copywriting generation, ClauseGuard compliance checks) and slower form submissions (multi-photo uploads, listing updates, trash/clarification actions) currently have uneven loading feedback:
- `#verifyComplianceBtn`, `#btnSaveListingChanges`, clarification forms, marketplace link forms, and modal confirmation buttons give **no spinner, no text swap, and no double-submit lock**.
- `#aiBtn` ("Generate with AI") swaps its icon for a static `⏳` hourglass without a skeleton placeholder where the title/description/price fields will appear.
- `/intake/` "Identify product" swaps the small trigger button, references a missing `#identifyHelpText` element in DOM, and shows **no placeholder skeleton, staged progress, or elapsed timer** inside the advisory area below — leaving assistants unsure whether a 4–8 second Gemini Vision request is actively progressing or stalled.
- Navigating back via browser history (`bfcache`) can leave form submit buttons stuck in a disabled loading state.

**Resolved Design (3-Layer Zero-Dependency Architecture):**
1. **Layer 1 — Global Declarative Form Feedback (`base.html`):**
   - Expose `window.AppFeedback` (`setButtonLoading`, `resetButtonLoading`, `resetAll`, `createStagedProgressController`) backed by CSS utilities in `base.html` (`animate-shimmer` using GPU-accelerated `transform`, `@media (prefers-reduced-motion: reduce)` support).
   - Attach a delegated `submit` handler on POST forms with `data-loading-text` on submit buttons (respecting `e.defaultPrevented`, HTML5 validation, and `data-confirm-message` modals whose confirmation runs via `btnProceedActionConfirm`), locking duplicate submissions via `form.dataset.appSubmitting`, applying `aria-busy="true"`, preserving any `name`/`value` payload on clicked submitters before asynchronous `disabled = true`, and automatically calling `window.AppFeedback.resetAll()` on `pageshow` (`bfcache` restoration).
2. **Layer 2 — Rich Non-Blocking AI Progress & Skeletons (`intake.html` & `product_detail.html`):**
   - Keep the rest of the UI readable (photos, raw notes, form context remain visible; NO full-screen dimmed overlay blocking context).
   - On `/intake/`, render a dedicated `#aiIdentificationSkeleton` card (`role="status"`, `aria-live="polite"`, `aria-busy="true"`) inside the advisory zone during `formState === 'identifying'`, showing staged progress messages (`Uploading & optimizing photos...` → `Identifying brand, specs & condition...` → `Checking prices & ClauseGuard rules...`), a live `tabular-nums` elapsed timer (`0s`, `1s`, ...), and layout-matched shimmer bars for title, attributes, and dual MSRP/Resale price blocks. Also render `#identifyHelpText` cleanly under `#identifyBtn`.
   - On `/products/<pk>/`, upgrade `#aiForm` / `#aiBtn` with an inline SVG spinner and display a non-blocking `#aiGeneratingSkeleton` banner above the Listing Copy inputs while `#productStagingForm` fields stay visible/read-only-safe until reload.
3. **Layer 3 — Consistent Uniform Coverage Across Action Buttons:**
   - Wire `data-loading-text` across `#submitBtn` (intake save), `#verifyComplianceBtn`, `#btnSaveListingChanges`, `#btnUploadDetailPhotos`, clarification answer/add/doubt forms, restore/permanent-delete forms, add/edit marketplace link forms, `#btnConfirmDeleteProduct`, and `#btnProceedActionConfirm`.
   - Enforce OPPO A74 (`360x800` and `320x711`) zero horizontal overflow, clean Flex/Grid `min-w-0` wrapping for bilingual ES/EN labels, `>= 12px` typography, and high WCAG AA contrast on Slate/Emerald surfaces.

**Out of Scope:**
- Fake percentage progress bars disconnected from real backend stages or WebSockets/SSE streaming endpoints (current HTTP endpoints return complete responses in one round-trip, so timed staged labels + live elapsed timer accurately convey wait duration without unnecessary server infrastructure).
- Blocking fullscreen modals for async actions.
