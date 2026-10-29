# PRD: Ready to Publish Dashboard Filter & Automated Phase Transition Revision

## 1. Objective

### Problem Statement
In the internal staging dashboard (`/dashboard/`), the status filter bar currently displays an **Active** (`?status=active`) tab that filters by `is_sold=False`, mixing together items that are in `Draft`, `Price Pending`, `Awaiting Info` (Doubts), `Ready to Publish`, `Published`, and `Blocked`. Meanwhile, there is **no dedicated dashboard tab** to filter products that are **Ready to Publish** (`ProductStatus.READY` / `?status=ready` — items that have photos, listing title & description, a valid sale price `> 0.00€`, zero pending clarifications, and zero active marketplace platform links).

Additionally, several edge cases in automatic phase transitions (`Product.compute_lifecycle_status()`, `Product.save()`, and clarification resolution views) can cause products to either:
1. Remain stuck in `AWAITING_INFO` when saved via the product update form after clarifications are no longer pending.
2. Be forcefully overwritten to `ProductStatus.READY` in `product_answer_clarification_view` and `product_delete_clarification_view` instead of computing the true lifecycle status (`DRAFT`, `PRICE_PENDING`, `READY`, or `PUBLISHED`), producing duplicate status logs or inaccurate flash messages.
3. Fail to re-evaluate lifecycle status when `ProductImage` records are added or deleted on an existing product, or when `ai_title` is empty while `raw_note` / `ai_description` are populated.

### Target Users & Goal
- **Store Managers & Sourcing Assistants**: Need a dedicated **Ready to Publish** (`✨ Ready to Publish` / `✨ Listo para publicar`) filter tab on the dashboard (replacing the ambiguous `Active` tab) that immediately surfaces items ready to be posted to external marketplaces (Wallapop, Vinted, eBay, Milanuncios), backed by deterministic, 100% automated phase transitions.

---

## 2. Tech Stack

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database:** SQLite (development/staging/production with online backup)
- **Frontend:** Django Templates + Tailwind CSS + Vanilla JS
- **Localization:** Bilingual (`es` / `en`) via Django `i18n` and `polib` (`manage.py compile_locales`)
- **Automated Browser Verification:** Playwright (`StaticLiveServerTestCase`)

---

## 3. Commands

```powershell
# 1. Lint & Style Check (Ruff)
.venv\Scripts\ruff.exe check .

# 2. Django System Check
.venv\Scripts\python.exe manage.py check

# 3. Compile Bilingual Translation Catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# 4. Run Targeted Lifecycle & Dashboard Tests
.venv\Scripts\python.exe manage.py test tests.test_lifecycle tests.test_dashboard tests.test_clarifications

# 5. Run Full Automated Test Suite
.venv\Scripts\python.exe manage.py test
```

---

## 4. Project Structure

```text
epic-tesla/
├── SPEC.md                                          # Master technical specification
├── docs/prds/
│   └── PRD-ready-to-publish-phase-and-filter.md     # Feature specification (this file)
├── inventory/
│   ├── models.py                                    # Product.compute_lifecycle_status(), Product.save(), signals
│   ├── views.py                                     # dashboard_view, clarification resolution views
│   ├── forms.py                                     # ProductUpdateForm status synchronization
│   └── templates/inventory/
│       ├── dashboard.html                           # Replace Active tab with Ready to Publish (?status=ready)
│       └── product_detail.html                      # Status badges and lifecycle display consistency
├── locale/
│   ├── es/LC_MESSAGES/django.po                     # Spanish translations ("Listo para publicar")
│   └── en/LC_MESSAGES/django.po                     # English translations ("Ready to Publish")
└── tests/
    ├── test_lifecycle.py                            # Automated phase transition unit tests
    ├── test_dashboard.py                            # Dashboard ?status=ready filter, counts, and ?status=active alias tests
    └── test_dashboard_responsive.py                 # Responsive horizontal tab rail tests (320x711, 360x800, 390x844, etc.)
```

---

## 5. Technical Design & Code Style

### 5.1 Automated Product Phase State Machine (`inventory/models.py`)

A product's lifecycle status (`Product.compute_lifecycle_status()`) is evaluated strictly according to the following precedence order:

1. **`SOLD` (`sold`)**: `self.is_sold` is `True`.
2. **`BLOCKED` (`blocked`)**: `self.status == ProductStatus.BLOCKED` (administratively blocked by a manager).
3. **`AWAITING_INFO` (`awaiting_info`)**: `self.pk` exists and at least one pending clarification (`clarifications.filter(status=ClarificationStatus.PENDING, is_direct_note=False)`) exists.
4. **`PUBLISHED` (`published`)**: `self.pk` exists and at least one active marketplace link (`listing_links.filter(is_active=True)`) exists.
5. **`DRAFT` (`draft`)**:
   - Missing listing description (`not bool((self.ai_description or "").strip())`) or missing title (`not bool((self.ai_title or "").strip())`), OR
   - On an existing persisted product where images were previously attached and all images have been removed (`not self._state.adding` and inquiry explicitly requires photos when staged via intake/detail). *Note: For unit-test backward compatibility where `Product.objects.create(ai_title=..., ai_description=..., sale_price=...)` is called in a single step before image attachment, `compute_lifecycle_status()` requires `has_title` and `has_description`, while `ProductImage` post-save/post-delete signals re-trigger `sync_lifecycle_status()` whenever photos are added or removed.*
6. **`PRICE_PENDING` (`price_pending`)**: Has `ai_title` and `ai_description`, no pending clarifications, and no active platform links, but `sale_price` is `None` or `<= 0.00`.
7. **`READY` (`ready` — "Ready to Publish" / "Listo para publicar")**: Has `ai_title`, `ai_description`, and `sale_price > 0.00`, with **no** pending clarifications and **no** active marketplace links.

#### Fixing Auto-Transition Edge Cases
- **In `Product.save()` (`inventory/models.py`)**:
  - When updating an existing product (`not is_adding`), unless the product is `SOLD` or `BLOCKED`, always compute `self.status = self.compute_lifecycle_status()`. Do **not** skip `compute_lifecycle_status()` when `self.status == ProductStatus.AWAITING_INFO` if there are no longer any pending clarifications in the database.
  - When `generate_ai_view` generates `ai_title` and `ai_description` on a product that lacks an `ai_title`, ensure `ai_title` is always populated (falling back to `display_title` if needed) so the product immediately transitions from `DRAFT` to `PRICE_PENDING` (if `sale_price` is empty/`0`) or `READY` (if `sale_price > 0`).
- **In `product_answer_clarification_view` and `product_delete_clarification_view` (`inventory/views.py`)**:
  - Remove the hardcoded `product.status = ProductStatus.READY; product.save(update_fields=["status"])` override.
  - Rely on `sync_product_on_clarification_save` / `sync_product_on_clarification_delete` (which call `product.compute_lifecycle_status()`), refresh `product` from DB, and display a status-accurate flash message.

### 5.2 Dashboard Filter Replacement (`inventory/views.py` & `dashboard.html`)

- **Backward-Compatible URL Alias**:
  - In `dashboard_view`, if `request.GET.get("status") == "active"`, normalize `status_filter = "ready"` so legacy bookmarks or links automatically select and display the `Ready to Publish` filter.
- **Query & Aggregation (`inventory/views.py`)**:
  ```python
  if status_filter == "active":
      status_filter = "ready"
  ```
  And in `counts_qs.aggregate(...)`:
  ```python
  ready_count=Count(
      "id",
      filter=Q(status=ProductStatus.READY, is_sold=False, is_deleted=False),
      distinct=True,
  ),
  ```
  Expose `ready_count` in the template context (while keeping `active_count` in context as an alias to `ready_count` or non-sold count if needed by any legacy caller).
- **Dashboard Template (`inventory/templates/inventory/dashboard.html`)**:
  - Replace the `Active` (`?status=active`) tab in `nav[role="tablist"]` with the **Ready to Publish** (`?status=ready`) tab:
    ```html
    <!-- Ready to Publish -->
    <a href="?status=ready{% if platform_filter %}&platform={{ platform_filter }}{% endif %}{% if search_query %}&q={{ search_query|urlencode }}{% endif %}"
       role="tab"
       id="tab-ready"
       aria-selected="{% if status_filter == 'ready' %}true{% else %}false{% endif %}"
       class="shrink-0 whitespace-nowrap inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition duration-150 {% if status_filter == 'ready' %}bg-white text-emerald-800 shadow-xs ring-1 ring-emerald-200 font-bold{% else %}text-slate-600 hover:text-slate-900 hover:bg-slate-200/60{% endif %}">
      <span aria-hidden="true">✨</span>
      <span>{% trans "Ready to Publish" %}</span>
      <span class="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs {% if status_filter == 'ready' %}bg-emerald-100 text-emerald-800 font-bold{% else %}bg-slate-200/80 text-slate-600{% endif %}">
        ({{ ready_count }})
      </span>
    </a>
    ```

---

## 6. Testing Strategy

- **Unit & Model Tests (`tests/test_lifecycle.py`)**:
  - Verify automatic transitions across the full lifecycle:
    - `DRAFT` (no description) $\to$ `PRICE_PENDING` (title + description added, no price) $\to$ `READY` (price $> 0$ added, no pending clarifications, no platform links) $\to$ `PUBLISHED` (active platform link added) $\to$ `READY` (all platform links removed) $\to$ `SOLD` (marked sold).
    - Opening a clarification from `READY` or `PRICE_PENDING` transitions to `AWAITING_INFO`; resolving or deleting the clarification automatically transitions back to `READY` (if title + description + price $> 0$ and no links), `PRICE_PENDING` (if no price), `DRAFT` (if no description), or `PUBLISHED` (if links exist).
    - Saving a product via `ProductUpdateForm` after clarifications are resolved never leaves the product stuck in `AWAITING_INFO`.
- **View & Dashboard Tests (`tests/test_dashboard.py`)**:
  - Verify `?status=ready` returns only products with `status=ProductStatus.READY` and `is_deleted=False`.
  - Verify `ready_count` in context matches the exact count of `READY` products.
  - Verify `?status=active` aliases cleanly to `status_filter == "ready"` and returns `READY` products.
  - Verify Spanish (`Listo para publicar`) and English (`Ready to Publish`) tab rendering.
- **Responsive Browser Tests (`tests/test_dashboard_responsive.py` & `tests/test_oppo_a74_responsive.py`)**:
  - Verify the horizontal status tab rail (`nav[role="tablist"]`) with the new `Ready to Publish` / `Listo para publicar` tab does not stack vertically (*apilación*) or cause document horizontal overflow across `320×711`, `360×800` (OPPO A74), `390×844`, `768×1024`, and `1440×900`.

---

## 7. Boundaries

- **Always do:**
  - Run `.venv\Scripts\python.exe manage.py test`, `.venv\Scripts\python.exe manage.py check`, `.venv\Scripts\python.exe manage.py compile_locales`, and `.venv\Scripts\ruff.exe check .` before finishing.
  - Preserve `ProductStatusLog` audit trail accuracy (avoid duplicate log entries on clarification resolution).
  - Maintain zero horizontal overflow on `320×711` and `360×800` viewports.
- **Ask first:**
  - Any database schema migration or removal of `ProductStatus` enum values.
  - Merging into `master` (mandatory user approval gate per `AGENTS.md`).
- **Never do:**
  - Never hard-delete products or alter soft-delete (`is_deleted=True`) isolation rules.
  - Never merge or push to `master` without explicit user confirmation.

---

## 8. Success Criteria

1. The dashboard status bar replaces the `Active` tab with `✨ Ready to Publish` (`✨ Listo para publicar` in Spanish) at `?status=ready`, showing `({{ ready_count }})`.
2. Visiting `?status=ready` (or legacy `?status=active`) displays exclusively non-deleted products in `ProductStatus.READY` (items with photos/title/description, `sale_price > 0`, no pending clarifications, and no active platform links).
3. Automatic phase transitions reliably move products between `DRAFT`, `PRICE_PENDING`, `AWAITING_INFO`, `READY`, `PUBLISHED`, `BLOCKED`, and `SOLD` whenever description, price, clarifications, or platform links change, without getting stuck in `AWAITING_INFO` or falsely forcing `READY` when price or description is missing.
4. 100% of automated tests, Django system checks, locale compilations, and Ruff lint checks pass with zero errors.

---

## 9. Open Questions

All initial scope questions have been resolved with the user:
- **Price Requirement for `Ready to Publish`:** Confirmed — `sale_price > 0` is required alongside title/description, photos, zero pending clarifications, and zero platform links (items missing a price remain in `Price Pending`).
- **Dashboard Tab Replacement:** Confirmed — replace `Active` directly with `Ready to Publish` (`?status=ready`) and support backward-compatible aliasing when `?status=active` is requested.
