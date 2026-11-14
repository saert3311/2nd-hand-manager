# PRD: Action Progress & Non-Blocking Loading Feedback System (Phase 54)

## 1. Objective & Background
Users operating on warehouse Wi-Fi / Android smartphones (e.g., OPPO A74) frequently trigger actions whose latency ranges from 400ms (database updates, photo uploads) to 4–8 seconds (Gemini Multimodal Vision identification, full SEO listing generation, ClauseGuard Stage 2 compliance verification). Missing or inconsistent feedback causes double-clicks, duplicate form submissions, confusion over whether the app froze, and stuck buttons after browser Back navigation (`bfcache`).

Phase 54 delivers a uniform, accessible, zero-dependency **Action Progress & Non-Blocking Loading Feedback System** across `base.html`, `intake.html`, `product_detail.html`, and related action forms (`dashboard.html`, `pallets.html`, `pallet_edit.html`, `provider_edit.html`).

---

## 2. Functional Requirements

### 2.1 Global Declarative Loading Engine (`inventory/templates/inventory/base.html`)
- **`window.AppFeedback` API**:
  - `setButtonLoading(btn, loadingText)`:
    - Saves original button HTML (`dataset.originalHtml`) and `aria-label`/`aria-busy` state cleanly once.
    - Injects a compact inline SVG spinner (`animate-spin`, `aria-hidden="true"`) paired with the localized `loadingText` inside a `min-w-0` span so button heights stay stable without layout jumps or mobile horizontal overflow.
    - Sets `aria-busy="true"` and `data-loading-active="true"`, marks `btn.classList.add("opacity-85", "cursor-wait")`, and queues `btn.disabled = true` on the next macrotask (`setTimeout(..., 0)`) so clicked `<button name="..." value="...">` submitters still transmit their form key/value pair before becoming disabled.
  - `resetButtonLoading(btn)`: Restores original button markup, clears `aria-busy`, `disabled`, `data-loading-active`, and transient loading classes.
  - `resetAll()`: Resets every `button[data-loading-active="true"]`, `[data-loading-form]`, and AI progress skeleton controller so browser Back (`pageshow` with `event.persisted` or normal bfcache restore) never leaves stale spinners or locked buttons.
  - `createStagedProgressController({ containerEl, labelEl, timerEl, stages })`:
    - Drives live elapsed seconds (`0s`, `1s`, `2s`, ... in `tabular-nums`) and cycles descriptive localized stage messages (`[0s, 2.5s, 5.5s, ...]`) until `.stop()` is called, exposing `.start()` and `.stop()` with full timer cleanup.
- **Delegated Form Submit Guard**:
  - Listens on `document` `"submit"`:
    - Ignores `if (e.defaultPrevented) return;`.
    - Ignores unconfirmed modal forms (`form.hasAttribute("data-confirm-message") && form.dataset.confirmed !== "true"`).
    - Blocks duplicate submissions if `form.dataset.appSubmitting === "true"` (`e.preventDefault()`).
    - When submitting, locates the triggering submitter (`e.submitter || form.querySelector('button[type="submit"][data-loading-text]')`), marks `form.dataset.appSubmitting = "true"`, and if `submitter` has `data-loading-text`, calls `AppFeedback.setButtonLoading(submitter, submitter.getAttribute("data-loading-text"))`.
- **Shimmer Animation & Reduced Motion CSS**:
  - Adds lightweight `@keyframes appShimmer` using GPU-composited `transform: translateX(...)` inside `.app-shimmer-bar::after`, automatically paused under `@media (prefers-reduced-motion: reduce)`.

### 2.2 Non-Blocking AI Progress & Skeleton Cards
1. **Intake AI Pre-Flight Identification (`inventory/templates/inventory/intake.html`)**:
   - Render `#identifyHelpText` (`<p id="identifyHelpText" class="text-xs sm:text-sm text-slate-500 mt-1.5" aria-live="polite">`) right below `#identifyBtn` so existing and new JS references reliably update real visible UI.
   - Add `#aiIdentificationSkeleton` (`role="status"`, `aria-live="polite"`, `aria-busy="true"`, `hidden` by default) directly above `#aiAdvisoryBanner`:
     - Clean Slate surface (`bg-slate-50 border border-slate-200 rounded-xl p-3 sm:p-4 space-y-3`) matching `#aiAdvisoryBanner`'s layout size (header title shimmer + pill shimmer, attribute lines, 2-column MSRP/Resale placeholder tiles).
     - Live status header displaying an inline SVG spinner, `#aiIdentifyStageText` cycling through localized stages (`Uploading & preparing photos...` → `Identifying brand, model & condition...` → `Estimating resale prices & policy rules...`), and a live `font-mono tabular-nums` counter (`#aiIdentifyElapsed`, e.g., `0s`, `1s`).
   - Rest of `/intake/` stays readable and unblocked while AI runs (only photo mutation controls and `#submitBtn` lock).
   - Hide `#aiAdvisoryBanner` when starting a fresh identification so stale prior results never overlap `#aiIdentificationSkeleton`, and always call `stop()` + hide `#aiIdentificationSkeleton` in `finally` regardless of JSON success, API error banner, or network failure.
2. **Product Detail AI Copywriting & Compliance (`inventory/templates/inventory/product_detail.html`)**:
   - Upgrade `#aiForm` / `#aiBtn` submit handler: replace static `⏳` with clean SVG spinner via `AppFeedback.setButtonLoading`, display `#aiGeneratingSkeleton` (`role="status"`, `aria-live="polite"`, `aria-busy="true"`) inside `#workspacePanelListing` right above the Listing Copy inputs, with staged copywriting steps (`Analyzing photos & notes...` → `Drafting SEO title & description...` → `Formatting tags & details...`) and live `tabular-nums` elapsed timer (`#aiGenerateElapsed`).
   - Annotate `#verifyComplianceBtn` (`Verify Compliance (AI)`) with `data-loading-text="{% trans 'Checking compliance...' %}"` and `#btnConfirmVerify` / `#btnSaveListingChanges` / `#btnUploadDetailPhotos` consistently.

### 2.3 Uniform Action Button Coverage
- Annotate POST form submit buttons with localized `data-loading-text`:
  - `intake.html`: `#submitBtn` (`{% trans "Saving product..." %}`) alongside its multi-photo submit lock.
  - `product_detail.html`: `#verifyComplianceBtn`, `#btnSaveListingChanges`, `#btnUploadDetailPhotos`, direct note & doubt submit buttons, clarification answer buttons, restore / permanent-delete / platform-sync buttons, Add & Edit marketplace link modal submit buttons, `#btnConfirmDeleteProduct`, and `#btnProceedActionConfirm` (handling programmatic `pendingConfirmForm.submit()`).
  - `dashboard.html`, `pallets.html`, `pallet_edit.html`, `provider_edit.html`: trash empty/cleanup buttons, pallet/provider create & save buttons.

---

## 3. Accessibility, Design & Mobile Requirements (OPPO A74 Baseline)
- **Zero Horizontal Overflow (`360×800` and `320×711`)**: Skeleton cards, staged status headers, and loading buttons must use `min-w-0`, `flex-wrap` or compact grid cells, and `break-words` so longer Spanish translations never clip or trigger `scrollWidth > clientWidth`.
- **WCAG 2.1 AA**:
  - Skeleton containers use `role="status"`, `aria-live="polite"`, and `aria-busy="true"`.
  - No sub-12px micro-fonts (`>= text-xs` / `12px`).
  - Contrast `>= 4.5:1` for stage labels and timers (`text-slate-700`, `text-slate-900` on `bg-slate-50`/`bg-white`).
  - Respect `@media (prefers-reduced-motion: reduce)`.
- **No Native Blocking Dialogs**: Never use `alert()` or `confirm()`.

---

## 4. Verification & Acceptance Criteria
1. Declarative `data-loading-text` attributes, `window.AppFeedback`, `#aiIdentificationSkeleton`, `#aiGeneratingSkeleton`, and `#identifyHelpText` are present and cleanly translated (`es`/`en`, compiled via `manage.py compile_locales`).
2. Browser verification (Playwright) proves:
   - Intercepted/delayed `/intake/identify/` shows `#aiIdentificationSkeleton` with non-zero bounding box, incrementing elapsed seconds (`0s` → `1s+`), `aria-busy="true"`, and non-hidden screen photos/notes, then hides skeleton and reveals `#aiAdvisoryBanner` upon completion.
   - Product detail `#aiForm` shows `#aiGeneratingSkeleton` and spinner on `#aiBtn`, while unconfirmed `data-confirm-message` modals do NOT stick buttons in loading state when cancelled.
   - Zero horizontal overflow (`document.documentElement.scrollWidth <= document.documentElement.clientWidth`) on both `360×800` and `320×711` viewports during loading states.
   - `pageshow` restores any active loading buttons to normal interactive state.
3. `ruff check .`, `manage.py check`, `manage.py makemigrations --check --dry-run`, `manage.py compile_locales`, and `manage.py test` pass 100%.
