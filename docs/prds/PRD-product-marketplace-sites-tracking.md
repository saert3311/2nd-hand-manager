# Product Requirements Document (PRD): Marketplace Sites & Product Listing Links Tracking

## 1. Executive Summary
Provide a flexible system to track the external marketplaces where products are published (e.g., Wallapop, Vinted, eBay, Milanuncios). Store managers can configure and manage supported marketplace platforms dynamically via the Django Administration panel (`/admin/`), and team members can view, add, update, and open published listing links directly on the product detail page (`/products/<pk>/`).

---

## 2. Problem Statement
Currently:
1. **No External Listing Tracking:** After staging an item with AI-generated title, description, and downloaded photos, managers or listers post the item on external platforms (Wallapop, Vinted, eBay, etc.), but there is no mechanism to record where the item was published or store the listing URLs.
2. **Loss of Listing Reference:** Team members have no way to verify whether an item is live on a given platform, check its external status, or correlate incoming buyer inquiries with the staging inventory.
3. **Hardcoded Platforms Risk:** If marketplace platforms are hardcoded as model choices or static fields, adding a new platform (e.g. Todocoleccion, Vestiaire Collective, Etsy) requires database schema migrations, code edits, and deployments.
4. **Scattered Links:** Without a centralized interface on the product detail page, retrieving or copying listing URLs across different marketplaces is manual and error-prone.

---

## 3. User Personas & Scenarios

### Persona: Store Manager / Lister (User B)
- **Scenario 1 (Publishing on Multiple Platforms):** The manager copies the AI copy, downloads photos, and posts the item on Wallapop and Vinted. On the product staging page (`/products/<pk>/`), they paste the respective listing URLs into the Wallapop and Vinted link inputs and save. The page displays direct clickable links and one-click copy buttons for each platform.
- **Scenario 2 (Adding a New Marketplace Platform):** The business starts cross-listing vintage luxury items on Vestiaire Collective. The manager opens `/admin/`, navigates to "Marketplace Sites", clicks "Add Marketplace Site", inputs "Vestiaire Collective", sets base URL `https://www.vestiairecollective.com`, and saves. Vestiaire Collective immediately becomes available as an option across all product detail pages without code changes.
- **Scenario 3 (Deactivating a Platform):** A marketplace is deprecated or paused. The manager unchecks `is_active` in Django Admin. The platform is hidden from new link additions while existing historical links remain preserved.
- **Scenario 4 (Verifying Active Listings):** When an item is marked as sold, the manager consults the listing links on the product page to quickly open and delete or mark the item sold on each external site.

### Persona: Field Sourcing Assistant (User A)
- **Scenario 5 (Viewing Published Links):** An assistant views a catalog item and can see where the item is currently listed for sale, with clickable links to the live ads.

---

## 4. Scope & Functional Requirements

### 4.1 Data Models (`inventory/models.py`)

#### Model 1: `MarketplaceSite`
Stores configurable marketplace platforms:
- `name`: `CharField(max_length=100, unique=True, verbose_name=_("Site Name"))` (e.g., "Wallapop", "Vinted", "eBay", "Milanuncios")
- `slug`: `SlugField(max_length=100, unique=True, blank=True, verbose_name=_("Slug"))` (auto-populated slug for unique reference and styling hooks)
- `base_url`: `URLField(max_length=255, blank=True, default="", verbose_name=_("Base URL"))` (e.g., `https://es.wallapop.com`)
- `is_active`: `BooleanField(default=True, db_index=True, verbose_name=_("Is Active"))` (controls visibility in product link forms)
- `order`: `PositiveIntegerField(default=0, verbose_name=_("Display Order"))` (controls display ordering)
- `created_at`: `DateTimeField(auto_now_add=True)`
- `updated_at`: `DateTimeField(auto_now=True)`

Meta:
- Ordering: `["order", "name"]`
- Verbose names localized in Spanish and English.

#### Model 2: `ProductListingLink`
Stores individual product publication links on specific marketplace sites:
- `product`: `ForeignKey(Product, on_delete=models.CASCADE, related_name="listing_links", verbose_name=_("Product"))`
- `site`: `ForeignKey(MarketplaceSite, on_delete=models.CASCADE, related_name="product_links", verbose_name=_("Marketplace Site"))`
- `url`: `URLField(max_length=1000, verbose_name=_("Listing URL"))`
- `is_active`: `BooleanField(default=True, verbose_name=_("Is Active Listing"))`
- `created_at`: `DateTimeField(auto_now_add=True)`
- `updated_at`: `DateTimeField(auto_now=True)`

Meta:
- Ordering: `["site__order", "site__name"]`
- Unique constraint: `UniqueConstraint(fields=["product", "site"], name="unique_product_site_link")` (one link per marketplace platform per product).

### 4.2 Django Admin Interface (`inventory/admin.py`)

- **`MarketplaceSiteAdmin`:**
  - Registered with `ManagerAdminSite` (`admin_site`).
  - Gated to managers (`is_manager(user)`).
  - List display: `name`, `slug`, `base_url`, `is_active`, `order`, `links_count`, `updated_at`.
  - List editable: `is_active`, `order` for rapid operational adjustments.
  - Search fields: `name`, `slug`, `base_url`.
  - Prepopulated fields: `{"slug": ("name",)}`.
  - Actions: Bulk activate and bulk deactivate platforms.

- **`ProductListingLinkInline` on `ProductAdmin`:**
  - Tabular inline on `ProductAdmin` allowing managers to view and edit external links directly within the standard Django admin product change form.

### 4.3 Product Detail Page UI & Workflow (`/products/<pk>/`)

- **Dedicated "Marketplace Links" Card:**
  - Placed prominently within the product detail / staging page (`product_detail.html`).
  - Displays all active marketplace sites.
  - For sites with saved links:
    - Platform badge / name.
    - Clickable external link (with external link icon, opening securely in `_blank` with `rel="noopener noreferrer"`).
    - Quick "Copy URL" button.
    - Inline edit / remove controls for managers.
  - For sites without saved links:
    - Quick input or "+ Add Link" action to paste the URL.
  - Supports updating links in batch or through a seamless form submission.
- **Role Permissions:**
  - Managers can create, update, and delete links.
  - Assistants can view links in read-only mode (clickable external links to verify listings).

### 4.4 Initial Data Seeding
- Data migration pre-populating default platforms:
  1. **Wallapop** (`https://es.wallapop.com`, order=1)
  2. **Vinted** (`https://www.vinted.es`, order=2)
  3. **Milanuncios** (`https://www.milanuncios.com`, order=3)
  4. **eBay** (`https://www.ebay.es`, order=4)

### 4.5 Internationalization (i18n)
- Complete bilingual support (Spanish & English):
  - Model field names, help text, and verbose names.
  - Admin list displays, fieldsets, and action descriptions.
  - Product page UI labels, button text, and copy feedback.
  - Translation catalog compiled using Python-native `compile_locales`.

---

## 5. Non-Functional Requirements
- **Security:** Validate all URLs with Django's `URLValidator` to prevent injection or javascript pseudoprotocols.
- **Relational Integrity:** Cascading deletion when a product is deleted; safe cascade or protect behavior when a marketplace platform is deactivated.
- **Performance:** Prefetch `listing_links` and related `site` objects (`prefetch_related('listing_links__site')`) on `product_detail_view` to prevent N+1 queries.
- **Maintainability:** Separation of concerns between model definitions, form validation, and template presentation.

---

## 6. Success Criteria
1. Store managers can add, edit, reorder, and deactivate marketplace sites in `/admin/`.
2. Initial migrations seed Wallapop, Vinted, Milanuncios, and eBay automatically.
3. On `/products/<pk>/`, managers can input, edit, and remove URLs for any active marketplace site.
4. Saved links render as clickable external links with opening in new tab and one-click copy buttons.
5. In Django Admin's product change page, an inline table displays and edits marketplace links.
6. Deactivated sites do not show up as new link options on the product detail page, but existing links remain accessible.
7. Attempting to add duplicate links for the same site on a single product is prevented by database constraint and form validation.
8. Full bilingual support in English and Spanish across Admin and Product Detail views.
9. 100% of automated unit and integration tests pass with zero regressions.
