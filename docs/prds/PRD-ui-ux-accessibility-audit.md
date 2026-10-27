# PRD-ui-ux-accessibility-audit: Comprehensive UI/UX Design System, Usability & Accessibility (WCAG 2.1 AA) Audit & Remediation

**Status:** Draft / Approved for Planning  
**Phase:** Phase 39 (Vertical Slice 35)  
**Branch:** `feat/ui-ux-accessibility-audit`  
**Target Standard:** WCAG 2.1 AA / 2.2 AA, `AGENTS.md` Engineering Conventions & `modern-web-guidance`

---

## 1. Executive Summary & Audit Scope

A comprehensive UI/UX and Frontend Accessibility (a11y) audit was conducted across both core surfaces of the **2ndHand Staging Hub & Rápido Pack Storefront** (`epic-tesla`):

1. **Internal Staff Hub (`inventory/templates/`)**:
   - Global App Shell & Navigation (`inventory/base.html`)
   - Authentication & Bot Protection (`registration/login.html`, `admin/login.html`)
   - Catalog Staging Dashboard (`inventory/dashboard.html`)
   - Mobile-First Product Intake (`inventory/intake.html`)
   - Product Detail Staging Workspace (`inventory/product_detail.html`, `inventory/forms.py`)
2. **Public Storefront (`storefront/templates/`)**:
   - Storefront Shell & Stitch Design System (`storefront/base_public.html`)
   - Corporate Landing Page (`storefront/home.html`)
   - Filterable Marketplace Catalog (`storefront/catalog.html`, `partials/_product_card.html`)
   - Public Product Detail & Conversion Workspace (`storefront/product_detail.html`, `partials/_purchase_box.html`, `partials/_how_to_buy_modal.html`)
   - Standalone Informational & Legal Pages (`storefront/how_to_buy.html`, `storefront/legal_page.html`)

---

## 2. Detailed Findings by Dimension

### Dimension 1: Visual & Design System (Hierarchy, Spacing, Typography, Color & Contrast)

#### 1.1 Visual Hierarchy
- **Strengths**:
  - Primary focal points on `intake.html` (photo dropzone + AI pre-flight flow), `dashboard.html` (filter rail + 4-column card grid), and `storefront/product_detail.html` (60/40 gallery + sticky WhatsApp buy box) are clear and purpose-driven.
- **Issues Found**:
  - **[V-01] Missing `<h1>` on `registration/login.html` & `inventory/product_detail.html`**:
    - `registration/login.html` starts with `<h2>{% trans "Sign in to your account" %}</h2>` (no `<h1>` on the page).
    - `inventory/product_detail.html` uses `<h2>` for section cards (`Photos`, `Marketplace Listing Copy`, `Marketplace Listing Links`) and never renders a primary `<h1>` for the product title/workspace header, violating WCAG 1.3.1 / `frontend-ui-engineering` heading hierarchy rules.
  - **[V-02] Skipped Heading Levels (`<h1>` → `<h3>`)**:
    - `inventory/intake.html` jumps from `<h1>New Product Intake</h1>` directly to `<h3>You have X product clarification...</h3>` and `<h3>Your Recent Uploads</h3>` (skipping `<h2>`).
    - `inventory/dashboard.html` jumps from `<h1>Inventory Catalog</h1>` to `<h3>No products found</h3>` in the empty state.
    - `storefront/partials/_how_to_buy_modal.html` and `image-lightbox-dialog` use `<h3>` as the dialog title without a preceding `<h2>`/`<h1>`.

#### 1.2 Spacing & Grid Consistency
- **Strengths**:
  - Consistent 4px/8px (`0.25rem`/`0.5rem`) Tailwind spacing scale (`gap-2`, `p-4`, `p-5`, `p-6`, `rounded-xl`, `rounded-2xl`) across both apps.
  - Dashboard status rail properly uses `overflow-x-auto flex-nowrap whitespace-nowrap no-scrollbar` to prevent vertical stacking (*anti-apilación*).
- **Issues Found**:
  - **[V-03] Invalid Tailwind Utility `py-0.2`**:
    - `inventory/base.html` (line 119) uses `py-0.2` on the doubts counter pill (`px-1.5 py-0.2`), which is not a valid Tailwind CSS class (`py-0.5` is the 2px step).
  - **[V-04] Sticky Category Rail Offset Mismatch on Mobile (`storefront/catalog.html`)**:
    - `catalog.html` (line 72) sets `sticky top-[108px]` on the category rail. However, on mobile (`< 768px`), `base_public.html` renders the top announcement bar + `h-20` (80px) navbar + mobile search bar (~48px) = ~156px height, causing the sticky category rail to tuck *underneath* the sticky header when scrolling down on mobile.

#### 1.3 Typography, OS Text Scaling & Sub-12px Micro-Fonts
- **Strengths**:
  - `inventory/base.html` includes `<meta name="text-scale" content="scale">` and mobile `@media (max-width: 640px)` rules enforcing `font-size: 1rem !important` on form controls to prevent iOS Safari auto-zoom.
- **Issues Found**:
  - **[V-05] Fixed `px` Font Tokens & Missing `<meta name="text-scale">` in `storefront/base_public.html`**:
    - Per `modern-web-guidance` (`typography` and `respect-os-text-scale`), font sizes should use relative `rem` units rather than fixed `px` so they scale with browser/OS accessibility preferences, and `<meta name="text-scale" content="scale">` should be present in `<head>`.
    - `storefront/base_public.html` defines all custom `fontSize` tokens in `px` (`"11px"`, `"12px"`, `"13px"`, `"14px"`, `"16px"`, `"20px"`, etc.) and lacks `<meta name="text-scale" content="scale">` and mobile 16px input protection.
  - **[V-06] Violation of `AGENTS.md` Rule: "No Sub-12px Micro-Fonts (`text-[10px]`, `text-[11px]`)"**:
    - `AGENTS.md` explicitly mandates: *"Avoid arbitrary micro-font classes (`text-[10px]`, `text-[11px]`); use `text-xs sm:text-sm` or larger."*
    - Found **26 occurrences** of `text-[10px]`, `text-[11px]`, and `11px` (`label-sm` token) across `inventory/base.html`, `inventory/dashboard.html`, `inventory/intake.html`, `inventory/product_detail.html`, `storefront/base_public.html`, `storefront/catalog.html`, `storefront/product_detail.html`, and `storefront/partials/_product_card.html`.

#### 1.4 Color & Contrast (WCAG AA 4.5:1 Normal Text / 3:1 Large Text & UI Components)
- **Strengths**:
  - Primary emerald (`#059669` / `#047857`) and deep teal (`#005c55` / `#0f766e`) palettes on light surfaces generally provide strong contrast.
- **Issues Found**:
  - **[V-07] Low Contrast Brand Green `#25D366` with White Text (`2.1:1` Ratio — Fails WCAG AA)**:
    - Throughout `storefront/` (`base_public.html`, `home.html`, `catalog.html`, `how_to_buy.html`, `_product_card.html`, `_purchase_box.html`, `_how_to_buy_modal.html`), WhatsApp CTAs use `bg-[#25D366] text-white` (or `text-on-primary`).
    - Luminance of `#25D366` is `0.485`; contrast against `#FFFFFF` is **2.10:1** (fails WCAG AA 4.5:1 for normal text and 3.0:1 for large/bold text).
    - **Fix**: Pair `#25D366` with dark high-contrast text (`text-[#052e16]` / `text-slate-950`, contrast **9.4:1**) or use a darker accessible WhatsApp green (`bg-[#128C7E]` or `bg-[#15803d]` with white text, contrast **> 4.5:1**).
  - **[V-08] Low Contrast Amber Badge `bg-[#F59E0B] text-surface-container-lowest` (`2.15:1` Ratio — Fails WCAG AA)**:
    - In `_product_card.html` (line 30) and `intake.html` / `product_detail.html` (`bg-amber-500 text-white`), white text on `#F59E0B` (`amber-500`) has a contrast ratio of **2.15:1**.
    - **Fix**: Use dark text (`text-amber-950` / `text-slate-950` on `bg-amber-400`/`bg-amber-500`, contrast **> 8:1**) or `bg-amber-700 text-white` (contrast **5.0:1**).
  - **[V-09] Low Contrast Footer & Muted Metadata (`text-slate-400` on `bg-white` / `bg-slate-50` — `2.5:1` Ratio)**:
    - `inventory/base.html` footer (`text-slate-400`), section headers in mobile drawer (`text-slate-400`), and `dashboard.html` ("No price set", dates, empty photo icon) use `text-slate-400` (`#94a3b8`), which has only **2.56:1** contrast on white (fails WCAG AA 4.5:1).
    - **Fix**: Upgrade readable text from `text-slate-400` to `text-slate-500` (`#64748b`, **4.76:1** on white) or `text-slate-600` (`#475569`, **7.58:1**).
  - **[V-10] Storefront Logo Secondary Text `text-secondary-container` (`#fe932c`) on White (`2.26:1` Ratio)**:
    - In `storefront/base_public.html` (lines 195, 336), the word `Pack` uses `text-secondary-container` (`#fe932c`) on white (`#ffffff`), yielding **2.26:1**. Using `text-secondary` (`#904d00`, **6.2:1**) or `text-[#c25e00]` (**4.52:1**) preserves the warm orange brand accent while passing WCAG AA.

---

### Dimension 2: Usability & Interaction (Affordance, States, Form Validation, Cognitive Load)

#### 2.1 Touch Target Sizes & Affordance (Minimum 44×44px on Mobile, 24×24px WCAG 2.2 AA Floor)
- **Strengths**:
  - Mobile drawer links (`min-h-[44px]`) and hamburger toggle (`w-11 h-11` = 44×44px) in `inventory/base.html` are well-sized.
- **Issues Found**:
  - **[U-01] Undersized Interactive Touch Targets (< 44×44px on Mobile)**:
    - `storefront/base_public.html`: Language switcher buttons (`ES` / `EN`, `px-1.5 py-0.5` ≈ 24×20px), mobile quick-link pills (`py-1`), and mobile "Guide" button (`py-1.5` ≈ 30px height).
    - `storefront/catalog.html`: Price & Condition filter pills (`px-space-sm py-1` ≈ 26px height) and Category rail pills (`py-space-xs` ≈ 28px height).
    - `inventory/base.html`: Flash message dismiss `&times;` button and global push banner dismiss button have no minimum hit area (`text-lg leading-none` without `w-8 h-8` / `min-h-[44px]`).
    - `inventory/intake.html` & `inventory/product_detail.html`: Reorder arrow buttons (`w-6 h-6` = 24px) and delete photo buttons (`w-6 h-6` = 24px) on thumbnails are tightly packed on mobile touchscreens; expanding hit areas (`min-w-[32px] min-h-[32px]` or `w-7 h-7` with padding) improves tap accuracy.

#### 2.2 Interactive States & Violation of `AGENTS.md` Rule ("Never Use Native `alert()` or `confirm()`")
- **Strengths**:
  - `intake.html` implements a comprehensive 3-state machine (`idle`, `identifying`, `submitting`) and accessible inline alert banner (`#intakeClientAlert`).
  - Soft-delete of a product uses a semantic modal (`#deleteProductModal`).
- **Issues Found**:
  - **[U-02] Blocking Native Browser `alert()` and `confirm()` in `inventory/product_detail.html`**:
    - `AGENTS.md` Section 4 explicitly mandates: *"Never use blocking browser `alert()` or `confirm()`. Use inline accessible banners (`role="alert"`, `aria-live="polite"`) or semantic modal dialogs (`role="dialog"`, `aria-modal="true"`)."*
    - **Line 192**: Deleting a product photo uses `onsubmit="return confirm('Are you sure you want to delete this photo?');"`.
    - **Line 377**: Dismissing a pending clarification uses `onclick="return confirm('Dismiss this clarification question?');"`.
    - **Line 436**: Deleting a clarification note uses `onclick="return confirm('Delete this clarification note?');"`.
    - **Line 1088**: Removing a marketplace link uses `onclick="return confirm('Are you sure you want to remove this link?');"`.
    - **Line 1411**: `copyToClipboard()` calls `alert("{% trans 'Nothing to copy!' %}")` when the input is empty!
    - **Fix**: Replace `alert()` in `copyToClipboard()` with inline button feedback (`⚠️ Empty` / status banner) and replace the 4 inline `confirm()` calls with a reusable, accessible confirmation `<dialog>` modal in `product_detail.html`.

#### 2.3 Form & Validation UX
- **Issues Found**:
  - **[U-03] Missing Field-Level Error Rendering & Programmatic Association in `inventory/product_detail.html` and `inventory/intake.html`**:
    - In `product_detail.html` (Listing Staging Form, lines 777–1002), `form.non_field_errors`, `form.ai_title.errors`, `form.ai_description.errors`, `form.sale_price.errors`, and `form.status.errors` are **never rendered in the template**! If `ProductUpdateForm.clean()` raises the error on `status` (*"Cannot mark product as Ready to Publish while pending clarifications remain unresolved"*), the user only sees a generic flash banner or nothing near the field.
    - In `intake.html`, `form.raw_note.errors` is not rendered beneath `{{ form.raw_note }}`.
    - Inputs lacked `aria-invalid` / `aria-describedby` synchronization on validation errors (`accessible-error-announcement` guide).
  - **[U-04] Missing `autocomplete` Attributes on Login Forms (`registration/login.html`)**:
    - Per WCAG 1.3.5 (Identify Input Purpose) and `modern-web-guidance` (`accessibility`), `#id_username` requires `autocomplete="username"` and `#id_password` requires `autocomplete="current-password"`.

#### 2.4 Cognitive Load
- **Issues Found**:
  - **[U-05] Dense Multi-Card Information Architecture on `inventory/product_detail.html`**:
    - The product detail workspace stacks 6 major functional blocks across 2 columns. While well-organized for desktop power-users, visual scannability and form error visibility need clearer section headers (`<h1>` product header + inline error summary) and consistent spacing.

---

### Dimension 3: Accessibility (a11y — Semantics, Keyboard Focus, ARIA, Screen Readers)

#### 3.1 Skip Links & Landmarks (WCAG 2.4.1 Bypass Blocks)
- **Issues Found**:
  - **[A-01] Missing "Skip to main content" Link in Both `inventory/base.html` and `storefront/base_public.html`**:
    - Neither base template provides a keyboard skip link (`<a href="#main-content" class="sr-only focus:not-sr-only ...">`) before the sticky navigation header, forcing keyboard users to tab through 10+ header controls on every page load.
  - **[A-02] Multiple `<nav>` Landmarks Without Distinguishable `aria-label` (`inventory/base.html`)**:
    - `desktop-nav` (`<nav id="desktop-nav">`, line 101) has no `aria-label`, while `#mobile-menu` has `aria-label="Mobile navigation"`.

#### 3.2 Keyboard Navigation, Focus Rings & Custom Widgets
- **Issues Found**:
  - **[A-03]Focus Suppression (`focus:outline-none`) Without High-Contrast `:focus-visible` Ring**:
    - In `storefront/base_public.html` (lines 230, 306), the search `<input type="search">` applies `focus:outline-none`. While the desktop wrapper uses `focus-within:ring-2`, the mobile search wrapper (line 299) has **no `focus-within` ring**, making keyboard focus invisible on mobile viewports!
  - **[A-04] Custom Modals in `inventory/` Lack Focus Trap, Initial Focus Management & `<dialog>` Semantics**:
    - While `storefront/` uses native `<dialog closedby="any">`, `inventory/intake.html` (`#imagePreviewModal`) and `inventory/product_detail.html` (`#deleteProductModal`) use `<div class="fixed inset-0 hidden" role="dialog" aria-modal="true">`.
    - When `#deleteProductModal` opens, keyboard focus is **not** moved into the modal, **not** trapped inside, **not** closed on `Escape` key or backdrop click, and **not** returned to `#btnOpenDeleteModal` on close!
    - Similarly, `#imagePreviewModal` in `intake.html` does not move focus to the close button on open or restore focus on close.
  - **[A-05] Non-Interactive `<img class="gallery-view-trigger">` Used as Button in `inventory/product_detail.html` & `storefront/product_detail.html`**:
    - In `inventory/product_detail.html` (line 181), gallery thumbnails use `<img class="... cursor-pointer gallery-view-trigger">` inside a `<div>`. Keyboard users cannot `Tab` to thumbnails or press `Enter`/`Space` to switch the main preview image!
    - In `storefront/product_detail.html` (line 111), `#mainProductPhoto` has `onclick="openImageLightbox()"` on an `<img>` tag (though the adjacent zoom `<button>` provides keyboard access, making the image button-wrapped or keeping the zoom button clearly labeled is essential).
  - **[A-06] Incomplete `role="tablist"` / `role="tab"` Pattern in `inventory/dashboard.html` and `inventory/product_detail.html`**:
    - In `dashboard.html` (line 30), the status filter links are `<a>` tags that navigate to a new URL (`?status=...`). Per `modern-web-guidance` (`accessibility`), `role="tab"` requires JS arrow-key navigation and `role="tabpanel"` associations; for URL-based navigation filters, `<nav aria-label="...">` with `aria-current="page"` on the active `<a>` link is the semantically accurate pattern (while keeping `role="tablist"` / `aria-selected` only if required by existing test contracts, or adding `aria-controls` / `role="tabpanel"` on `#panelDirectNote` and `#panelAskDoubt` in `product_detail.html`).
  - **[A-07] Missing `aria-expanded` on Collapsible History Toggle (`#toggleStatusLogsBtn`) and Reorder Mode Toggle (`#toggleReorderModeBtn`)**:
    - In `product_detail.html`, `#toggleStatusLogsBtn` (line 692) expands/collapses `.extra-status-log` items without updating `aria-expanded="true|false"`.
    - `#toggleReorderModeBtn` (line 151) toggles reorder mode without `aria-pressed="true|false"`.

#### 3.3 Form Labels & ARIA Associations
- **Issues Found**:
  - **[A-08] Unassociated `<label>` Elements in `inventory/product_detail.html` & `inventory/intake.html`**:
    - `intake.html` (line 77): `<label>Photos (Required)</label>` has no `for="imageInput"` attribute.
    - `product_detail.html` (lines 487, 497, 521, 531, 559, 569): The 6 `<label>` elements for `category`, `note`, and `question` in the Clarifications Hub have **no `for` attributes** and the corresponding `<select>` and `<textarea>` inputs have **no `id` attributes**!
    - `product_detail.html` (line 393): The inline clarification answer `<input type="text" name="answer">` has **no `<label>` and no `aria-label`** (relying solely on `placeholder`, violating WCAG 3.3.2).
    - `product_detail.html` (line 1104): The marketplace URL `<input type="url" name="url">` has **no `<label>` and no `aria-label`** (relying solely on `placeholder`).
    - `product_detail.html` (lines 908, 914): `{{ form.sold_channel_type }}` meets `<label for="id_sold_channel_type">`, but `{{ form.sold_marketplace }}` has **no `<label>` or `aria-label`**.

#### 3.4 Decorative Icons, Emojis & Alt Text (WCAG 1.1.1 Non-text Content)
- **Issues Found**:
  - **[A-09] Unhidden Material Symbols Ligature Icons Read Aloud by Screen Readers (`storefront/`)**:
    - Across all `storefront/` templates (`base_public.html`, `home.html`, `catalog.html`, `product_detail.html`, `how_to_buy.html`, `legal_page.html`, and partials), `<span class="material-symbols-outlined">...</span>` is used **without `aria-hidden="true"`**.
    - Screen readers read the raw ligature text aloud before every button/link label (e.g., *"local underscore shipping View parcel services"*, *"storefront Store"*, *"military underscore tech LIKE NEW"*, *"manage underscore search See similar items"*).
    - **Fix**: Add `aria-hidden="true"` to all decorative `<span class="material-symbols-outlined">` elements.
  - **[A-10] Generic / Uninformative Image `alt` Attributes in `inventory/`**:
    - `intake.html` (line 264): Recent uploads thumbnail uses `alt="thumb"` instead of `alt="{{ prod.display_title }}"`.
    - `product_detail.html` (line 168): Featured image uses `alt="main"` instead of `alt="{{ product.display_title }}"`.
    - `product_detail.html` (line 181): Gallery thumbnails use `alt="thumb {{ forloop.counter }}"` instead of descriptive text (`{% trans "Photo" %} {{ forloop.counter }} - {{ product.display_title }}`).
  - **[A-11] Flash Messages & Dynamic Banners Missing Live Region Roles (`inventory/base.html`)**:
    - `#global-push-banner` (line 359) and `#flash-messages` (line 368) in `inventory/base.html` lack `role="status"` / `role="alert"` and `aria-live="polite"`, and their dismiss `&times;` buttons lack `aria-label="{% trans 'Dismiss notification' %}"`.

---

## 3. Objectives & Acceptance Criteria

1. **Zero Test Regressions**: Preserve all existing DOM IDs, CSS class hooks, and ARIA attributes asserted by the 300+ existing unit and browser tests (`badge-pending-clarifications`, `role="tablist"`, `set_language`, etc.).
2. **WCAG 2.1 AA Compliance**:
   - Every page has a skip-to-content link (`#main-content`) and a logical `<h1>` → `<h2>` → `<h3>` heading outline.
   - All text and interactive badges meet $\ge 4.5:1$ contrast (normal text) or $\ge 3:1$ (large/bold text).
   - All form controls have explicit `<label for="...">` or `aria-label`, `autocomplete` where appropriate, and visible + programmatic error states (`aria-invalid`, `aria-describedby`).
   - All decorative Material Symbols icons and emojis are hidden from assistive technology (`aria-hidden="true"`), and all `<img>` tags have meaningful `alt` text.
   - All modals manage keyboard focus, `Escape` dismissal, and backdrop clicks without native browser `alert()` or `confirm()`.
   - Both `inventory/` and `storefront/` opt into OS text scaling (`<meta name="text-scale" content="scale">`), use relative `rem` font sizes, and eliminate sub-12px micro-fonts (`text-[10px]`, `text-[11px]`).
3. **Bilingual Completeness**: Any new accessibility labels (`Skip to main content`, `Dismiss notification`, confirmation dialog texts) are localized in `es` and `en` and compiled via `manage.py compile_locales`.
