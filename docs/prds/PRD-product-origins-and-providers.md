# PRD: Product Origins & Providers (Phase 51)

## 1. Objective

### Problem Statement
In **2ndHand Staging Hub**, Phase 46 introduced `Pallet` tracking for bulk liquidation pallets, while non-pallet inventory fell into a generic `"No Pallet (Individual Item)"` bucket. However, inventory comes from multiple commercial sources beyond anonymous pallets:
1. **Liquidation & Wholesale Suppliers (`WHOLESALER`)**: Pallets originate from specific suppliers (e.g., *LiquiStock*, *Amazon Returns ES*), and the store also purchases loose wholesale lots from those same suppliers outside of numbered pallets.
2. **In-Store Walk-In Buyouts (`WALK_IN`)**: Customers bring individual secondhand items directly into the Alfafar store for cash buyouts (*Compra en Tienda / Particular*).

Without a `Provider` hierarchy co-living with `Pallet` tracking:
- Managers cannot trace which supplier delivered a pallet or which channel supplied a standalone item.
- Managers cannot measure true **Provider ROI & Performance** (total acquisition cost across pallets + loose/walk-in buyouts vs. realized sales revenue and active catalog value).
- Sourcing Assistants would be slowed down if forced to pick from two separate dropdowns on narrow mobile viewports (`360×800` and `320×711` OPPO A74).

### Target Users & Goals
- **Store Managers (`managers` group / `is_staff` / `is_superuser`)**:
  - Manage `Provider` records (`Wholesale / Liquidation`, `In-Store Walk-In / Individual`, `Other`) inside the unified **Pallets & Providers** workspace (`/pallets/?tab=providers`) and Django Admin (`ProviderAdmin`).
  - Link any `Pallet` to its `Provider`, automatically cascading that provider to every `Product` assigned to that pallet.
  - Record an optional Manager-only `acquisition_cost` (€) on individual non-pallet `Product` records inside `/products/<pk>/` (strictly hidden from Sourcing Assistants).
  - View **Provider ROI & Performance** cards (Total Cost without double-counting, Realized Sales Revenue, Net Margin, Active Stock Value, Pallet count, Active/Sold item counts).
  - Filter the staging dashboard (`/dashboard/`) by `Provider` (`?provider=<id>` or `?provider=none`), composable with `Pallet`, `Status`, `Platform`, `Channel`, `Compliance`, and Search filters.
- **Sourcing Assistants (`assistants` group / `is_assistant`)**:
  - Zero extra friction on `/intake/`: interact with **one single sticky Origin dropdown (`#id_origin`)** grouped cleanly into **Active Pallets** (`pallet:<id>`) and **Direct Origins — No Pallet** (`provider:<id>`), remembering the last selected origin across consecutive uploads (`last_intake_origin`).
  - Commercial confidentiality: `Provider` management, `Pallet.purchase_price`, `Pallet.estimated_value`, and `Product.acquisition_cost` are strictly hidden and blocked (`403 Forbidden` on management routes) for assistants.

---

## 2. Tech Stack

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database:** SQLite with zero-downtime online backup
- **Frontend:** Django Templates + Tailwind CSS + Vanilla JS (OPPO A74 responsive baseline `320×711` & `360×800`)
- **Localization:** Bilingual (`es` / `en`) via Django `i18n` and `polib` (`manage.py compile_locales`)
- **Testing:** Automated unit, integration, permission, and Playwright responsive tests (`manage.py test`)

---

## 3. Commands

```powershell
# 1. Lint & Style Check (Ruff)
.venv\Scripts\ruff.exe check .

# 2. Django System Check
.venv\Scripts\python.exe manage.py check

# 3. Create & Apply Migrations
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate

# 4. Compile Bilingual Translation Catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# 5. Run Targeted & Full Test Suite
.venv\Scripts\python.exe manage.py test tests.test_product_origins_providers tests.test_pallet_tracking
.venv\Scripts\python.exe manage.py test
```

---

## 4. Architecture & Domain Reference

### 4.1 Domain Models (`inventory/models.py`)

1. **`ProviderType(models.TextChoices)`**:
   - `WHOLESALER = "wholesaler", _("Wholesale / Liquidation Supplier")`
   - `WALK_IN = "walk_in", _("In-Store Walk-In / Individual")`
   - `OTHER = "other", _("Other Origin")`

2. **`Provider(models.Model)`**:
   - `name`: `CharField(max_length=120, unique=True)`
   - `slug`: `SlugField(max_length=120, unique=True, blank=True)` (auto-populated from `name` on save)
   - `provider_type`: `CharField(max_length=20, choices=ProviderType.choices, default=ProviderType.WHOLESALER, db_index=True)`
   - `contact_info`: `CharField(max_length=255, blank=True, default="")`
   - `notes`: `TextField(blank=True, default="")`
   - `is_active`: `BooleanField(default=True, db_index=True)`
   - `created_by`: `ForeignKey(AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL)`
   - `created_at` / `updated_at`
   - **Data Migration Seed**: Pre-seeds `Compra en Tienda / Particular` (`slug="compra-en-tienda-particular"`, `provider_type=WALK_IN`, `is_active=True`) so walk-in buyouts never create duplicate per-person provider records.

3. **`Pallet` Extension (`inventory/models.py`)**:
   - `provider`: `ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="pallets")`
   - **Cascade Invariant**: When `Pallet.provider` changes on save, all linked `Product` records (`pallet_id=self.pk`) automatically sync their `provider_id` to `self.provider_id`.

4. **`Product` Extensions (`inventory/models.py`)**:
   - `provider`: `ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")`
   - `acquisition_cost`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.00), MaxValueValidator(9999999.99)])` — strictly Manager-only cost for non-pallet items.
   - **Golden Sync Invariant in `Product.save()`**: Whenever `product.pallet_id` is set, `product.provider_id` automatically inherits `product.pallet.provider_id`. When `product.pallet_id` is `None`, `product.provider_id` retains the direct origin.

### 4.2 Provider ROI Formula (No Double-Counting)
For any `Provider`:
$$\text{Total Cost} = \sum_{\text{pallet} \in \text{provider.pallets}} \text{pallet.purchase\_price} + \sum_{\substack{\text{prod} \in \text{provider.products} \\ \text{is\_deleted=False, pallet IS NULL}}} \text{prod.acquisition\_cost}$$
$$\text{Realized Revenue} = \sum_{\substack{\text{prod} \in \text{provider.products} \\ \text{is\_deleted=False, is\_sold=True}}} \text{prod.sale\_price}$$
$$\text{Active Stock Value} = \sum_{\substack{\text{prod} \in \text{provider.products} \\ \text{is\_deleted=False, is\_sold=False}}} (\text{prod.sale\_price} \text{ or } \text{prod.estimated\_resale\_price} \text{ or } 0)$$
$$\text{Net Margin} = \text{Realized Revenue} - \text{Total Cost}$$

### 4.3 URL Routes (`inventory/urls.py`)
- `/pallets/` (`inventory:pallets`) — Unified Pallets & Providers Hub (`?tab=pallets` / `?tab=providers`).
- `/pallets/<int:pk>/edit/` (`inventory:pallet_edit`) — Edit Pallet (including `provider` assignment).
- `/pallets/<int:pk>/delete/` (`inventory:pallet_delete`) — Non-destructive delete Pallet (`POST`).
- `/pallets/providers/create/` (`inventory:provider_create`) — Create Provider (`POST`, Manager-only).
- `/pallets/providers/<int:pk>/edit/` (`inventory:provider_edit`) — Edit Provider (`GET`/`POST`, Manager-only).
- `/pallets/providers/<int:pk>/delete/` (`inventory:provider_delete`) — Non-destructive delete Provider (`POST`, Manager-only).

### 4.4 Security, Privacy & Storefront Firewall
- `Provider` routes and all cost metrics (`Pallet.purchase_price`, `Pallet.estimated_value`, `Product.acquisition_cost`, Provider ROI totals) are gated with `@manager_required` and omitted from Assistant-accessible views (`/intake/`, `/dashboard/`, `/products/<pk>/` when `not can_manage`).
- Public Storefront (`storefront/views.py`) excludes `provider_id`, `pallet_id`, and `acquisition_cost` from `SAFE_PUBLIC_PRODUCT_FIELDS` and clears them in `_sanitize_public_product()`.

### 4.5 Mobile Ergonomics (OPPO A74 `360×800` & `320×711` Baseline)
- Zero horizontal overflow (`scrollWidth <= clientWidth`) on `/intake/`, `/dashboard/`, `/products/<pk>/`, `/pallets/`, `/pallets/?tab=providers`, and `/pallets/providers/<pk>/edit/`.
- Minimum `16px` font size on `<select>` and `<input>` controls on viewports `<= 640px` (`text-base sm:text-sm`).
- Single-tap `<optgroup>` sticky Origin dropdown on `/intake/` without crowding the top navbar.
