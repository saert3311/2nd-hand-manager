# Pallet Tracking & Sticky Intake Attribution

## Problem Statement
How might we attribute each intake product to its liquidation pallet without repetitive data entry on mobile, while giving managers a simple place to record pallet reception dates, purchase costs, and estimated values?

## Recommended Direction
Introduce a lightweight `Pallet` domain model managed exclusively by Store Managers on a dedicated `/pallets/` screen (and Django Admin), paired with a session-sticky Pallet selector on `/intake/` and a pallet field on the Product Detail staging workspace.

## Data Model
- **`Pallet`**:
  - `number`: `PositiveIntegerField(unique=True)` — Simple sequential pallet number (e.g. `1`, `2`, `15`).
  - `received_date`: `DateField(default=timezone.localdate)` — Date the pallet was received.
  - `purchase_price`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)` — Optional cost paid for the pallet (€).
  - `estimated_value`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)` — Optional estimated total value of the pallet (€).
  - `notes`: `TextField(blank=True)` — Optional notes or origin details.
  - `created_by` / `created_at`: Standard audit metadata.
- **`Product.pallet`**:
  - Nullable `ForeignKey(Pallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")`.

## MVP Scope (What's In)
1. **Manager Pallet Screen (`/pallets/`)**:
   - Single-screen creation form (auto-suggests next pallet number `max(number)+1` & today's date; optional `purchase_price` and `estimated_value`) + list/table of existing pallets with item count, reception date, and financials.
   - Link in top navbar for Managers only (`📦 Pallets` / `📦 Palés`).
2. **Sticky Pallet Selector on Intake (`/intake/`)**:
   - Dropdown showing `Pallet #<number> (<received_date>)` + explicit `— No Pallet (Individual Item) —`.
   - Defaults to `request.session["last_intake_pallet_id"]` if valid; otherwise defaults to the most recently created pallet.
   - Financial fields (`purchase_price`, `estimated_value`) are strictly hidden from Sourcing Assistants.
3. **Product Detail Workspace (`/products/<pk>/`)**:
   - Editable `pallet` selector in `ProductUpdateForm` for Managers.
   - Display pallet badge in product header and info blocks.
4. **Django Admin**:
   - `PalletAdmin` registration with item count badge and `pallet` filter/column in `ProductAdmin`.

## Not Doing (and Why)
- **No complex ROI dashboards or charts** — Keep the UI fast and focused on creation and attribution as requested.
- **No assistant pallet creation** — Prevents duplicate or disorderly pallet numbers and protects commercial financial data.
- **No mandatory pallet lock** — Walk-in, customer consignment, or standalone items can still be cataloged with "No Pallet".
- **No public storefront exposure** — Pallet data is strictly internal warehouse/inventory operational metadata.
