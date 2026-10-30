# PRD: Pallet Tracking & Sticky Intake Attribution (Phase 46)

## 1. Objective

### Problem Statement
In **2ndHand Staging Hub**, secondhand inventory is frequently acquired in liquidation pallets (or lots) containing dozens of varied products. When warehouse staff unpacks and catalogs a pallet using the mobile-first intake flow (`/intake/`), there is currently **no way to link products to their origin pallet**.

Without pallet attribution:
1. Managers cannot trace which physical pallet an item came from.
2. Managers cannot record what was paid for a pallet (`purchase_price`) or its estimated value (`estimated_value`) upon reception (`received_date`).
3. Assistants would be slowed down significantly if forced to manually type a pallet number for every single item on mobile.

### Target Users & Goals
- **Store Managers (`managers` group / `is_staff` / `is_superuser`)**:
  - Register new pallets on a dedicated screen (`/pallets/`) with an auto-incremented pallet number, reception date (defaults to today), optional purchase cost, optional estimated total value, and optional notes.
  - View the list of pallets with item counts and financial figures.
  - Edit or delete pallets (with non-destructive cascade protection: deleting a pallet does not delete its products, setting `product.pallet = None`).
  - View and change a product's attributed pallet in the Product Detail staging workspace (`/products/<pk>/`).
  - Full visibility and control in Django Admin (`PalletAdmin`).
- **Sourcing Assistants (`assistants` group / `is_assistant`)**:
  - Rapid, frictionless intake on mobile: A clean dropdown selector on `/intake/` defaults to the **sticky pallet** from their previous cataloged item (or the newest active pallet if none is in session).
  - Explicit option to select `— No Pallet (Individual Item) —` for walk-in purchases or standalone inventory.
  - Zero manual re-typing of pallet numbers across consecutive uploads.
  - **Commercial confidentiality**: Financial figures (`purchase_price`, `estimated_value`) and the `/pallets/` creation page are strictly inaccessible to assistants.

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

# 5. Run Targeted Test Suite
.venv\Scripts\python.exe manage.py test tests.test_pallet_tracking
```

---

## 4. Architecture & Domain Reference

### 4.1 Data Model: `Pallet` (`inventory/models.py`)
```python
class Pallet(models.Model):
    """
    Represents an acquired liquidation pallet or inventory lot.
    """
    number = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        verbose_name=_("Pallet Number"),
        help_text=_("Sequential pallet identification number"),
    )
    received_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
        verbose_name=_("Received Date"),
        help_text=_("Date when the pallet arrived at the warehouse"),
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("9999999.99")),
        ],
        verbose_name=_("Purchase Price (€)"),
        help_text=_("Acquisition cost paid for the pallet"),
    )
    estimated_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("9999999.99")),
        ],
        verbose_name=_("Estimated Value (€)"),
        help_text=_("Estimated total retail or resale value of the pallet"),
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Notes"),
        help_text=_("Optional supplier, manifest, or condition notes"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pallets",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
    )

    class Meta:
        ordering = ["-number"]
        verbose_name = _("Pallet")
        verbose_name_plural = _("Pallets")

    def __str__(self):
        return f"Pallet #{self.number} ({self.received_date})"
```

### 4.2 Product Association: `Product.pallet`
```python
pallet = models.ForeignKey(
    "Pallet",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="products",
    verbose_name=_("Pallet"),
    help_text=_("Origin liquidation pallet to which this product belongs"),
)
```
- Non-destructive deletion: Deleting a `Pallet` does not delete its products; it sets `product.pallet = None`.

---

## 5. User Workflows & View Endpoints

### 5.1 Manager Pallet Screen (`/pallets/`)
- Protected by `@login_required` and `@manager_required`.
- Sourcing assistants attempting access receive a `403 Forbidden` response.
- **Top Creation Form**:
  - Pre-fills `number` with `max(number) + 1` (or `1` if no pallets exist).
  - Pre-fills `received_date` with today (`timezone.localdate()`).
  - Fields: `number`, `received_date`, `purchase_price` (optional), `estimated_value` (optional), `notes` (optional).
  - Submitting POST creates the pallet and redirects with flash message.
- **Pallets List**:
  - Displays cards/table showing: Pallet Number badge, Received Date, Item Count (`products.count()`), Purchase Price, Estimated Value, Notes, and actions (Edit / Delete).
  - Empty state with guidance when no pallets have been created.
- **Pallet Edit / Delete**:
  - `/pallets/<pk>/edit/`: Modal or dedicated edit view for managers.
  - `/pallets/<pk>/delete/`: POST-only endpoint to remove pallet (leaving products intact with `pallet=None`).

### 5.2 Sticky Intake Attribution (`/intake/`)
- In `product_intake_view`:
  - When rendering the form, resolve initial pallet from session:
    1. If `request.session.get("last_intake_pallet_id")` is present and refers to an existing pallet, default to it.
    2. If session key is explicitly `"none"`, default to `None` ("No Pallet").
    3. If no session key exists, default to the latest created `Pallet` (or `None` if no pallets exist).
  - Include `pallet` in `ProductIntakeForm` as a `ModelChoiceField`:
    - Queryset: `Pallet.objects.order_by("-number")`.
    - Empty label: `— {% trans "No Pallet (Individual Item)" %} —`.
    - Custom label: `Pallet #%(number)s (%(date)s)` — zero financial figures exposed.
  - On valid form submission:
    - Save `product.pallet`.
    - Update `request.session["last_intake_pallet_id"] = product.pallet_id if product.pallet else "none"`.

### 5.3 Product Detail Staging Workspace (`/products/<pk>/`)
- In `ProductUpdateForm`: Add `pallet` field (optional dropdown) for Store Managers.
- Display pallet badge in product header and details summary: e.g. `📦 Pallet #14 (2026-10-31)`.

---

## 6. Mobile & Accessibility Constraints

- **OPPO A74 Baseline (`360×800` & `320×711`)**:
  - Single-line and fluid responsive layouts ensuring `document.documentElement.scrollWidth <= document.documentElement.clientWidth`.
  - All `<input>`, `<select>`, and `<textarea>` elements styled with `text-base sm:text-sm` to prevent iOS/Android zooming.
  - Minimum touch targets of at least `38px` / `40px` (`min-h-[38px]`).
- **Navigation**:
  - Add `📦 Pallets` link in the top navigation bar (`base.html`), visible only when `is_manager(request.user)`.

---

## 7. Success Criteria & Verification

1. **Manager Pallet Registration**: Store Manager can register Pallet #1 with received date and optional purchase price and estimated value.
2. **Sequential Auto-Numbering**: The next pallet defaults to #2.
3. **Sticky Intake**: Assistant opens `/intake/`, selects Pallet #1, catalogs Product A. Next intake automatically has Pallet #1 pre-selected.
4. **No-Pallet Choice**: Assistant can choose "No Pallet", and the next intake remembers "No Pallet".
5. **Commercial Privacy**: Assistant cannot see purchase price or estimated value anywhere in intake or detail, and `/pallets/` is 403 Forbidden for assistants.
6. **Cascade Safety**: Deleting a Pallet does not delete associated products; `product.pallet` becomes `None`.
7. **Full Quality Gate**: 100% of automated tests pass, 0 Ruff lint warnings, 0 Django check issues, bilingual translations compiled.
