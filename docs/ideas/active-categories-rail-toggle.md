# Active-Only Category Rail with Inline "Show All Categories" Toggle

## Problem Statement
How might we keep the Store Shelf category rail (`#categoryRail`) focused on categories that currently have available (`is_sold=False`) stock—preventing visitors from clicking into empty categories—while still giving visitors a one-click way to reveal all 12 official store categories in place?

## Recommended Direction
Filter the default visible chips in `#categoryRail` to categories with **`visible_count > 0` available (`is_sold=False`) products** (plus the currently selected `active_category`, when visiting an empty category URL directly), and append an inline **`+ Ver todas las categorías (X)`** (`+ See all categories (X)`) toggle button at the end of the rail:

1. **Available-Stock Counting (`storefront/views.py`)**:
   - Count only **available (`is_sold=False`)** publicly visible items per category (`Product.objects.public_visible().filter(is_sold=False)`), so sold-only categories are treated as 0 available stock by default.
   - Compute `hidden_categories_count` for all active categories that have `visible_count == 0` and are not currently selected (`cat.slug != active_category`).
2. **Progressive Disclosure in `#categoryRail` (`storefront/templates/storefront/catalog.html`)**:
   - Available categories render immediately with their live item count (`({{ cat.visible_count }})`).
   - Empty categories render with `hidden data-empty-category="true"` and muted styling (`text-outline opacity-65`) so expanding reveals all categories clearly while distinguishing in-stock vs. empty ones.
   - `#toggleAllCategoriesBtn` expands/collapses those empty categories in place without navigating away or introducing page horizontal overflow.

## Key Assumptions to Validate
- [x] If a visitor visits `/categoria/<slug>/` for an empty category directly, that active chip remains visible and highlighted before clicking `"Show all categories"`.
- [x] Sold-only items (`is_sold=True`) do not inflate a category as having active stock.

## MVP Scope
- `storefront/views.py` (`catalog_view`): filter `available_base_ids` to `is_sold=False` and pass `hidden_categories_count`.
- `storefront/templates/storefront/catalog.html`: hide `visible_count == 0` non-active categories by default, display counts (`text-xs`), and add `#toggleAllCategoriesBtn` + `toggleAllShelfCategories()`.
- `locale/` & `tests/test_storefront.py`: ES/EN translations (`"Show active only"` / `"Ver solo con stock"`) and automated unit tests covering available-only visibility, active empty category retention, and hidden category counts.

## Not Doing (and Why)
- **Not deactivating empty `Category` database rows** — categories remain active for `/sitemap.xml` and direct category bookmarks.
- **Not building a separate modal or category directory page** — inline expansion in `#categoryRail` keeps mobile (`320px`/`360px`) and desktop interactions minimal and instant.
