# Product Requirements Document (PRD) & Specification
# Sale Channel Tracking on Sold Products ("Where Was It Sold?")

## 1. Objective & Problem Statement

### 1.1 Problem Statement & Operational Background
Currently in the **2ndHand Staging Hub**:
1. When a product is marked as sold (`is_sold=True` or `status='sold'`), the application records `is_sold` and `sold_at` (timestamp), but **does not track where or through which commercial channel the product was sold**.
2. Products staged in the hub can be sold through multiple distinct channels:
   - **In-Store (Tienda física):** Walk-in customer purchases at the physical retail store.
   - **External Marketplaces:** Online platforms where the product was cross-listed (e.g. Wallapop, Vinted, eBay, Milanuncios, Vestiaire Collective, etc., dynamically managed via `MarketplaceSite`).
   - **Other / Direct Sales:** Direct sales (phone, social media, wholesale, pop-up events).
3. **Loss of Sales Channel Attribution:** Store managers cannot determine:
   - Which platforms or channels generate the most volume and revenue.
   - Which marketplace listing needs immediate manual delisting or archiving upon an in-store sale.
   - A clear audit trail of where a specific inventory item ended up.
4. **Missing Catalog Visibility:** The dashboard filter `?status=sold` displays all sold products in a single unsegmented list without showing or filtering by sale channel.

### 1.2 Objective
Implement comprehensive **Sale Channel Tracking** across the product lifecycle:
1. **Data Model Enrichment:** Extend `Product` with `sold_channel_type` (`in_store`, `marketplace`, `other`), `sold_marketplace` (`ForeignKey(MarketplaceSite, null=True, blank=True)`), and optional `sold_channel_notes` (`CharField` for order #, ticket reference, or buyer note).
2. **Interactive Detail View:** On the product detail page (`/products/<pk>/`), when a manager marks a product as sold or updates a sold listing, provide an intuitive UI to select the channel (In-Store vs. Marketplace site vs. Other), with quick-selection highlighting platforms where the product had active published links.
3. **Robust Form Validation:** Enforce that if a product is marked as `sold`, the manager must indicate the channel; and if `marketplace` is chosen, a valid marketplace platform must be specified.
4. **Dashboard Filtering & Badging:** Display clear channel badges (e.g. `🏪 Tienda`, `🌐 Wallapop`, `🏷️ Vinted`) on product cards, and allow sub-filtering sold products by channel on the catalog dashboard (`?status=sold&channel=in_store`, `?status=sold&channel=marketplace`, etc.).
5. **Django Admin Visibility:** Expose sale channels in `ProductAdmin` list display, filters, and fieldsets.
6. **Audit Trail Synchronization:** Record the sales channel and sale price in `ProductStatusLog` when transitioning to `sold`.
7. **Full Bilingual Support (i18n):** Complete localization in Spanish (`es`) and English (`en`).

---

## 2. Tech Stack & Architecture Context

- **Runtime / Framework:** Python 3.13, Django 5.1+
- **Database:** SQLite (local/dev/staging) / PostgreSQL (production-ready)
- **Relational Integrity:** Foreign key relationship from `Product.sold_marketplace` to `MarketplaceSite` with `on_delete=models.SET_NULL` so marketplace deletions do not destroy product sales history.
- **Frontend / Styling:** Django Templates + Tailwind CSS + Vanilla JS (progressive disclosure of channel dropdown when sold is checked).
- **Internationalization (i18n):** Django `gettext_lazy` and template `{% trans %}` / `{% blocktrans %}`.

---

## 3. Executable Commands

- **Run Dev Server:** `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
- **Create Migrations:** `.venv\Scripts\python.exe manage.py makemigrations inventory`
- **Apply Migrations:** `.venv\Scripts\python.exe manage.py migrate`
- **Run Targeted Tests:** `.venv\Scripts\python.exe manage.py test tests.test_sale_channel`
- **Run Full Test Suite:** `.venv\Scripts\python.exe manage.py test`
- **Code Linter:** `.venv\Scripts\ruff.exe check .`
- **Compile Translations:** `.venv\Scripts\python.exe manage.py compile_locales`

---

## 4. Project Structure & Affected Modules

```text
epic-tesla/
├── inventory/
│   ├── models.py                     # Add SaleChannelType, sold_channel_type, sold_marketplace, sold_channel_notes, helper properties
│   ├── forms.py                      # Update ProductUpdateForm with channel fields, conditional validation
│   ├── views.py                      # Update product_detail_view, dashboard_view channel filtering
│   ├── admin.py                      # Update ProductAdmin list_display, list_filter, fieldsets
│   ├── templates/inventory/
│   │   ├── product_detail.html       # Dynamic sale channel selector, sold badge display
│   │   └── dashboard.html            # Channel badges on product cards, sold sub-filter tabs/dropdown
│   └── migrations/
│       └── 0017_product_sale_channel.py # Schema migration for sale channel fields
├── locale/
│   └── es/LC_MESSAGES/django.po      # Spanish translation catalogs
├── tests/
│   └── test_sale_channel.py          # Unit & integration tests for sale channel workflows
├── docs/
│   └── prds/
│       └── PRD-sale-channel-tracking.md
└── SPEC.md                           # Update living specification
```

---

## 5. Detailed Functional Specifications

### 5.1 Data Models (`inventory/models.py`)

#### 5.1.1 `SaleChannelType` Enum
```python
class SaleChannelType(models.TextChoices):
    IN_STORE = "in_store", _("In-Store / Physical Store")
    MARKETPLACE = "marketplace", _("Online Marketplace")
    OTHER = "other", _("Other / Direct Sale")
```

#### 5.1.2 New Fields on `Product`
1. `sold_channel_type`:
   - `CharField(max_length=20, choices=SaleChannelType.choices, blank=True, db_index=True, verbose_name=_("Sale Channel Type"))`
   - Default: `""` (empty string for unsold or legacy unassigned products).
2. `sold_marketplace`:
   - `ForeignKey("MarketplaceSite", null=True, blank=True, on_delete=models.SET_NULL, related_name="sold_products", verbose_name=_("Sold Marketplace"))`
   - Nullable foreign key referencing the configured marketplace site where the item was sold.
3. `sold_channel_notes`:
   - `CharField(max_length=255, blank=True, default="", verbose_name=_("Sale Reference / Notes"), help_text=_("Optional ticket number, order ID, or buyer reference"))`

#### 5.1.3 Helper Methods & Properties on `Product`
- `sale_channel_display`:
  - Returns localized string representation of the channel:
    - If `not is_sold`: `""`
    - If `sold_channel_type == 'in_store'`: `_("In-Store")` / `_("Tienda física")`
    - If `sold_channel_type == 'marketplace'`: `self.sold_marketplace.name` if `self.sold_marketplace` else `_("Marketplace")`
    - If `sold_channel_type == 'other'`: `_("Other")` / `_("Otro")`
- `mark_as_sold(self, price=None, user=None, channel_type=None, marketplace=None, notes=None, commit=True)`:
  - Updates `is_sold=True`, `status=ProductStatus.SOLD`, `sold_at=timezone.now()`.
  - Sets `sold_channel_type`, `sold_marketplace`, and `sold_channel_notes`.
  - Records formatted audit log string in `_status_notes` (e.g. *"Sold in-store for €35.00"* or *"Sold on Wallapop for €40.00 (ref: #1234)"*).
- `mark_as_unsold(self, user=None, commit=True)`:
  - Reverts `is_sold=False`, computes lifecycle status, sets `sold_at=None`.
  - Clears `sold_channel_type=""`, `sold_marketplace=None`, `sold_channel_notes=""`.

### 5.2 Form Validations (`inventory/forms.py`)

In `ProductUpdateForm`:
1. Add form fields:
   - `sold_channel_type`: `forms.ChoiceField(choices=[("", "---")] + SaleChannelType.choices, required=False)`
   - `sold_marketplace`: `forms.ModelChoiceField(queryset=MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"), required=False)`
   - `sold_channel_notes`: `forms.CharField(max_length=255, required=False)`
2. Validation Rules (`clean` method):
   - When `is_sold` is `True` or `status == ProductStatus.SOLD`:
     - `sold_channel_type` is **mandatory**. If empty, raise validation error: `_("Please select where this product was sold.")`.
     - If `sold_channel_type == SaleChannelType.MARKETPLACE` and `sold_marketplace` is not provided:
       - Raise validation error on `sold_marketplace`: `_("Please select the marketplace platform where the product was sold.")`.
   - When `is_sold` is `False` and `status != ProductStatus.SOLD`:
     - Clean `sold_channel_type = ""`, `sold_marketplace = None`, `sold_channel_notes = ""` to ensure clean state if an item is reverted.

### 5.3 Staging Product Detail UI (`inventory/templates/inventory/product_detail.html`)

1. **Sold Status & Channel Section:**
   - In the "Sold Status" section:
     - Checkbox `#id_is_sold` ("Mark Product as Sold").
     - Container `#soldChannelContainer` (visible if `#id_is_sold` is checked, hidden otherwise):
       - Channel Selector: Segmented pills or `<select>` for `Tienda física`, `Marketplace`, `Otro`.
       - When `Marketplace` is selected, display dropdown `#id_sold_marketplace`.
       - **Published Platforms Quick-Picker:** If the product has published links (`product.listing_links.filter(is_active=True)`), display one-click buttons with badges: e.g. `[🏷️ Wallapop]` `[🏷️ Vinted]` allowing the manager to set the marketplace in one click.
       - Optional input: `Referencia / Notas de venta` (`#id_sold_channel_notes`).
2. **Sold Item Header / Badge:**
   - When product is already sold, render a clear status block:
     - Badge: `🏪 Vendido en Tienda física` or `🌐 Vendido en Wallapop`
     - Price: `€XX.XX`
     - Date: `25/10/2026 14:30`
     - Notes: Displayed if present (e.g. `Ref: Ticket #4592`).

### 5.4 Dashboard View & Catalog Filtering (`inventory/templates/inventory/dashboard.html` & `inventory/views.py`)

1. **Card Badges:**
   - On each sold product card, render the sale channel badge next to the sold badge:
     - `🏪 Tienda` (slate/emerald pill with store icon)
     - `🌐 Wallapop` / `🌐 Vinted` (distinct platform pill)
2. **Channel Filtering on Dashboard:**
   - When browsing the `Sold` status tab (`?status=sold`):
     - Provide sub-filter pills or a channel dropdown:
       - `Todos los canales (X)` (`?status=sold`)
       - `🏪 Tienda física (Y)` (`?status=sold&channel=in_store`)
       - `🌐 Marketplaces (Z)` (`?status=sold&channel=marketplace`)
       - Individual marketplace filter (`?status=sold&channel=marketplace&platform=wallapop`)
   - Preserve pagination and search terms across channel filters.

### 5.5 Django Administration Integration (`inventory/admin.py`)

1. `ProductAdmin.list_display`: Add `sale_channel_display_col` with icon badges.
2. `ProductAdmin.list_filter`: Add `sold_channel_type` and `sold_marketplace`.
3. `ProductAdmin.fieldsets`: Organize sale fields in a dedicated collapsible fieldset:
   ```python
   (_("Sale & Channel Details"), {
       "fields": ("is_sold", "sold_at", "sold_channel_type", "sold_marketplace", "sold_channel_notes"),
       "classes": ("collapse",),
   }),
   ```

### 5.6 Audit Trail & Lifecycle Sync (`ProductStatusLog`)

- In `Product.save()` and `Product.mark_as_sold()`:
  - Log trigger note: `Sold via {channel_display} for €{price} {notes}`.
  - Gives complete historical visibility into who recorded the sale, when, and via which channel.

---

## 6. Code Style & Example Snippet

```python
# inventory/models.py
class SaleChannelType(models.TextChoices):
    IN_STORE = "in_store", _("In-Store / Physical Store")
    MARKETPLACE = "marketplace", _("Online Marketplace")
    OTHER = "other", _("Other / Direct Sale")

# In Product model:
sold_channel_type = models.CharField(
    max_length=20,
    choices=SaleChannelType.choices,
    blank=True,
    default="",
    db_index=True,
    verbose_name=_("Sale Channel Type"),
    help_text=_("Channel through which the product was sold"),
)
sold_marketplace = models.ForeignKey(
    "MarketplaceSite",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="sold_products",
    verbose_name=_("Sold Marketplace"),
    help_text=_("Marketplace platform where the sale occurred"),
)
sold_channel_notes = models.CharField(
    max_length=255,
    blank=True,
    default="",
    verbose_name=_("Sale Reference / Notes"),
    help_text=_("Optional sale ticket #, buyer reference, or order note"),
)
```

---

## 7. Testing Strategy

1. **Model Tests (`tests/test_sale_channel.py`):**
   - Assert `mark_as_sold` correctly persists channel type, marketplace, and notes.
   - Assert `mark_as_unsold` resets channel fields cleanly.
   - Assert `sale_channel_display` returns accurate localized strings across all channel types.
   - Assert deleting a `MarketplaceSite` sets `sold_marketplace` to `NULL` without deleting the sold `Product` (`SET_NULL`).
2. **Form Validation Tests:**
   - Assert marking as sold without `sold_channel_type` raises a form validation error.
   - Assert selecting `marketplace` without a `sold_marketplace` raises a validation error.
   - Assert valid in-store and marketplace submissions save successfully.
3. **View & Filtering Tests:**
   - Assert `product_detail_view` POST saves sale channel and redirects cleanly.
   - Assert `dashboard_view` filters products by `?status=sold&channel=in_store` and `?status=sold&channel=marketplace`.
   - Assert channel counts are accurately calculated.
4. **Admin Tests:**
   - Assert `ProductAdmin` renders sale channel columns, filters, and fieldsets without permission errors.
5. **Localization Tests:**
   - Assert Spanish translations render correctly for all channel choices and error messages.

---

## 8. Boundaries

- **Always:**
  - Enforce referential safety (`SET_NULL` for `sold_marketplace`).
  - Validate channel requirements when an item is marked sold.
  - Run the full test suite (`python manage.py test`) before committing.
  - Update translation catalogs (`.po` and `.mo`).
- **Ask First:**
  - Making sale channel mandatory for existing historical sold products (legacy sold records will have `sold_channel_type=""`).
  - Changing external marketplace definitions or deleting marketplace platforms.
- **Never:**
  - Allow deleting a `Product` when its associated `MarketplaceSite` is deleted (`CASCADE` is strictly forbidden).
  - Break existing `is_sold` or `sold_at` fields relied on by search and reporting services.

---

## 9. Success Criteria (Reframed Concrete Conditions)

- [ ] Sourcing managers can mark a product as sold and record whether it was sold In-Store (`in_store`), on a Marketplace (`marketplace` + platform FK), or Other (`other`).
- [ ] If marked as sold, the UI rejects submission if no channel is selected.
- [ ] If marked as sold on a marketplace, the specific marketplace platform must be selected.
- [ ] The product detail page displays the channel, timestamp, and notes when viewing a sold product.
- [ ] The catalog dashboard (`/dashboard/?status=sold`) displays channel badges and supports sub-filtering by channel (`in_store` vs `marketplace`).
- [ ] Django Admin displays the sale channel in `ProductAdmin` list view and filters.
- [ ] 100% of automated tests pass (unit, integration, and linter).

---

## 10. Open Questions & Design Decisions

1. **Default Sale Channel Selection:**
   - When a manager checks "Mark Product as Sold", should the channel default to **Tienda física (In-Store)** (often the most frequent offline event), or should it require an explicit unselected choice (`--- Seleccionar canal ---`)?
   - *Recommendation:* Require explicit selection (`---`) to prevent accidental default tagging, with quick 1-click buttons for In-Store and any active platforms the product was listed on.
2. **Handling Legacy Sold Products:**
   - There are existing products in the database already marked as sold without channel information.
   - *Recommendation:* Allow `blank=True` in the model so legacy sold items remain valid with an unassigned channel (`-`), but enforce the channel in the form for any newly edited or newly marked sold products.
3. **Optional Sale Channel Notes:**
   - Is an optional `sold_channel_notes` field (e.g. ticket #, buyer name, order ID) desired?
   - *Recommendation:* Yes, a lightweight 255-character optional text field provides high practical utility for reconciliations.
