# Product Requirements Document (PRD) & Specification
# Public Marketplace Storefront Transformation — Rápido Pack (`rapidopack.es`, Phase 1 → Phase 2 Ready)

## 0. Capability Map & Module Decomposition

| Module ID | Responsibility | Depends On |
| :--- | :--- | :--- |
| `catalog-taxonomy` | `Category` (12 official families), `StorefrontConfiguration` singleton, `Product` marketplace fields (`category`, `condition`, `is_public`, `is_featured`, `is_reserved`, `reserved_until`, `views_count`, `whatsapp_clicks`), `ProductQuerySet.public_visible()`, and Gemini AI taxonomy extraction (`ai_service.py`) + staging UI/Admin controls | — |
| `storefront-public` | Dedicated `storefront` Django app, public URL routing (`/` corporate landing page, `/tienda/` marketplace catalog, `/tienda/categoria/<slug>/` category catalog, `/tienda/producto/<slug>-<pk>/` product detail, `/como-comprar/` how-to-buy page), Stitch-aligned `base_public.html` (`Outfit` + `Hanken Grotesk` + Teal `#005c55`/`#0f766e` palette), search/category/price/condition/sort filters, 2-col mobile / 4-col desktop grid, and decoupled `_purchase_box.html` + *"Saber más"* modal | `catalog-taxonomy` |
| `conversion-analytics` | First-party click-tracking redirect endpoints (`/go/whatsapp/`, `/go/whatsapp/<int:pk>/`, `/go/link/<int:link_pk>/`), `ProductClickEvent` / counter increments (`whatsapp_clicks`, `listing_links.clicks_count`), and conversion metrics display in the Manager Dashboard & Product Detail staging view | `catalog-taxonomy`, `storefront-public` |
| `seo-and-legal` | LocalBusiness JSON-LD on `/`, OpenGraph & WhatsApp rich link preview tags (`og:title`, `og:description`, `og:image`, `product:price:amount`), Schema.org `Product` JSON-LD (`InStock` / `SoldOut`, `UsedCondition`), `/sitemap.xml`, `/robots.txt`, and GDPR/LSSI legal pages (`/aviso-legal/`, `/privacidad/`, `/cookies/`) | `storefront-public` |

**Build Order:** `catalog-taxonomy` $\to$ `storefront-public` $\to$ `conversion-analytics`, `seo-and-legal`

---

## 1. Objective & Problem Statement

### 1.1 Problem Statement
Currently, `2ndHand Staging Hub` operates exclusively as a private, staff-only internal staging and cataloging tool (`@login_required` at `/`, `/dashboard/`, `/intake/`, `/products/<pk>/`). Potential buyers have no centralized public catalog to browse available inventory, filter by category/condition/price, or contact the store directly via WhatsApp or external marketplace listings (Wallapop, Vinted, eBay, Milanuncios).

### 1.2 Objective
Transform the platform into a **bilingual (ES/EN), mobile-first Public Marketplace Storefront** for **Rápido Pack (`rapidopack.es`)** — *"Tu tienda de segunda mano y oportunidad en Alfafar (Valencia) y online"* — while keeping the internal staff workflow (`/dashboard/`, `/intake/`, `/products/<pk>/`, Web Push, OCI backups) 100% intact.

- **Phase 1 (Current Scope):**
  1. **Corporate Business Landing Page (`/`), Public Marketplace Catalog (`/tienda/` & `/tienda/categoria/<slug>/`), & SEO Product Detail (`/tienda/producto/<slug>-<pk>/`)** faithfully implementing the Google Stitch reference designs ([`docs/stitch_references/`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/)) and the **Rápido Pack Curation System** ([`DESIGN_SYSTEM.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/DESIGN_SYSTEM.md)).
  2. **Landing Page Business Showcase (`/`):** Multi-carrier parcel point strip (`SEUR`, `GLS`, `InPost`, `Amazon Hub`, `Kanguro`, `DHL`, `Punto Pack Oficial`), 4 parcel service cards + 3-step workflow, brand story (*"Más que una tienda, tu punto de barrio"* + 4 pillars), 4 newest available products (*"Recién llegados"*), trust stats band, Alfafar location & schedule card, and `Schema.org/LocalBusiness` JSON-LD.
  3. **12 Official Categories & 4 Official Condition Grades** pre-seeded via migration and automatically classified by **Gemini Multimodal Vision AI** (`ai_service.py`) at zero extra API latency.
  4. **Public Visibility & 7-Day Sold Social Proof (`Product.objects.public_visible()`):** Automatically displays `READY` and `PUBLISHED` products with `is_public=True`, `sale_price > 0`, and non-empty `ai_title`, plus `SOLD` items from the last **7 days** pinned to the end of the catalog with a **"VENDIDO"** social-proof stamp.
  5. **Direct WhatsApp Conversion + External Platform Links + "Saber más" Modal & `/como-comprar/` Page:** Configurable WhatsApp number (`StorefrontConfiguration`), pre-filled WhatsApp inquiry message with `Ref. #<id>`, Precio Único policy, free in-store pickup in Alfafar (`Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia`), and tracked outbound buttons for active Wallapop/Vinted/eBay listings.
  6. **Strict Internal Data Firewall:** Zero exposure of `raw_note`, `ProductClarification` doubts, `created_by` usernames, or `ProductStatusLog` in any public HTML, JSON-LD, OpenGraph, or sitemap response.
- **Phase 2 Readiness (Zero-Refactor Bridge):**
  - Include `is_reserved` and `reserved_until` on `Product` for manual 24h holds in Phase 1 and atomic checkout locks in Phase 2.
  - Isolate conversion CTAs into `templates/storefront/partials/_purchase_box.html`.

---

## 2. Reference Designs & Questionnaires (Source of Truth)

1. **Client Questionnaire (100% Confirmed):** [`docs/questionnaires/client-storefront-questionnaire-es.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/questionnaires/client-storefront-questionnaire-es.md)
2. **Developer Architecture Questionnaire (100% Confirmed):** [`docs/questionnaires/developer-storefront-architecture-questionnaire.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/questionnaires/developer-storefront-architecture-questionnaire.md)
3. **Google Stitch Prompts:** [`docs/questionnaires/google-stitch-prompts.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/questionnaires/google-stitch-prompts.md)
4. **Google Stitch MCP Reference Screens (`projects/17041960214932697448`):**
   - [`docs/stitch_references/DESIGN_SYSTEM.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/DESIGN_SYSTEM.md) — *Rápido Pack Curation System* (`Outfit` + `Hanken Grotesk`, Primary Teal `#005c55` / `#0f766e`, Secondary Amber `#904d00` / `#fe932c` / `#F59E0B`, WhatsApp `#25D366`, Surface `#faf8ff` / `#ffffff`, On-Surface `#131b2e`)
   - [`docs/stitch_references/landing_page.html`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/landing_page.html) — Corporate Business Landing Page (`/` — Hero split layout, carrier logo strip, 4 parcel service cards + 3-step flow, *Quiénes somos* brand identity, 4 *Recién llegados* product cards, trust stats band, Alfafar map & contact card, final CTA banner, 4-col footer)
   - [`docs/stitch_references/desktop_catalog_homepage.html`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/desktop_catalog_homepage.html) — Desktop Marketplace Catalog (`/tienda/` — `1280px` max-w, 4-col product grid, sticky announcement & header, compact hero + 4 trust badges, horizontal 12-category rail, price & condition filter bar, Alfafar physical store banner, 3-col commercial footer)
   - [`docs/stitch_references/mobile_catalog_homepage.html`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/mobile_catalog_homepage.html) — Mobile Marketplace Catalog (2-col compact cards, touch-scrollable filter chips, floating WhatsApp CTA, mobile bottom navigation bar)
   - [`docs/stitch_references/product_detail_and_modal.html`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/product_detail_and_modal.html) & [`docs/stitch_references/product_detail_orbea.html`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/stitch_references/product_detail_orbea.html) — 60%/40% Desktop Product Detail (`/tienda/producto/<slug>-<pk>/` — `lg:col-span-7` gallery + verification box, `lg:col-span-5` sticky purchase box, outbound Wallapop/Vinted tiles, and interactive *"¿Cómo comprar en Rápido Pack Alfafar? (Saber más)"* modal)

---

## 3. Tech Stack & Executable Commands

- **Runtime / Framework:** Python 3.13+, Django 5.x
- **Database:** SQLite (with `PRAGMA journal_mode=WAL;` enabled on connection for high-concurrency public reads; PostgreSQL compatible)
- **Frontend:** Django Templates + Tailwind CSS CDN configured with Stitch theme tokens (`Outfit`, `Hanken Grotesk`, Material Symbols Outlined) + Vanilla JS
- **AI Integration:** `google-genai` structured outputs (`ProductListingSchema` extended with `category_slug` and `condition`)

### Commands
```bash
# Run Dev Server
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

# Create & Apply Migrations
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate

# Compile Bilingual Message Catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# Run Linter & System Check
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe manage.py check

# Run Full Automated Test Suite
.venv\Scripts\python.exe manage.py test
```

---

## 4. Project Structure & URL Routing

```text
epic-tesla/
├── config/
│   ├── settings.py               # Register 'storefront.apps.StorefrontConfig', SQLite WAL mode
│   └── urls.py                   # Include storefront.urls at '', inventory.urls at ''
├── inventory/
│   ├── models.py                 # Category, StorefrontConfiguration, ProductCondition, Product fields, ProductQuerySet.public_visible()
│   ├── forms.py                  # Add category, condition, is_public, is_featured, is_reserved to ProductUpdateForm
│   ├── views.py                  # Preserve /dashboard/, /intake/, /products/<pk>/; move staff root redirect to /panel/ (inventory:root)
│   ├── admin.py                  # CategoryAdmin, StorefrontConfigurationAdmin, updated ProductAdmin
│   └── services/
│       └── ai_service.py         # Extend ProductListingSchema & IntakePreflightSchema with official category_slug & condition
├── storefront/                   # NEW Django App for Public Marketplace Storefront
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py                   # '/', '/tienda/', '/tienda/categoria/<slug>/', '/tienda/producto/<slug>-<pk>/', '/como-comprar/', '/go/whatsapp/', '/go/whatsapp/<pk>/', '/go/link/<link_pk>/', '/sitemap.xml', '/robots.txt', '/aviso-legal/', '/privacidad/', '/cookies/'
│   ├── views.py                  # Public landing, catalog, category, product detail, how_to_buy, click redirectors, sitemap, robots, legal views
│   ├── context_processors.py     # Injects StorefrontConfiguration singleton into public templates
│   └── templates/
│       └── storefront/
│           ├── base_public.html              # Independent public layout (Stitch theme, Outfit/Hanken Grotesk, staff top bar)
│           ├── home.html                     # Corporate landing page (hero, parcel carriers, services, quiénes somos, 4 newest items, stats, map/contact)
│           ├── catalog.html                  # Public marketplace catalog (/tienda/ & /tienda/categoria/<slug>/)
│           ├── product_detail.html           # Public 60/40 product page (/tienda/producto/<slug>-<pk>/), gallery, JSON-LD, OpenGraph
│           ├── how_to_buy.html               # Standalone shareable "¿Cómo comprar?" page (/como-comprar/)
│           ├── legal_page.html               # Standard RGPD/LSSI legal templates (/aviso-legal/, /privacidad/, /cookies/)
│           └── partials/
│               ├── _product_card.html        # Responsive card supporting AVAILABLE, DESTACADO, RESERVADO, VENDIDO states
│               ├── _purchase_box.html        # Decoupled conversion box (Phase 1 WhatsApp + Marketplace links -> Phase 2 Cart)
│               └── _how_to_buy_modal.html    # "Saber más: ¿Cómo comprar en Rápido Pack Alfafar?" modal
└── tests/
    └── test_storefront.py        # Comprehensive unit, security (no-leak firewall), SEO, filter, and click-tracking tests
```

### URL Map (`config/urls.py`, `storefront/urls.py`, `inventory/urls.py`)
| Path | Name | Access | Behavior |
| :--- | :--- | :--- | :--- |
| `/` | `storefront:home` | Public (200 OK) | Corporate Business Landing Page: hero, carriers (`SEUR`, `GLS`, `InPost`, `Amazon Hub`, `Kanguro`, `DHL`, `Punto Pack`), parcel services (`#paqueteria`), Punto Pack (`#punto-pack`), brand identity (`#quienes-somos` / `#sobre-nosotros`), 4 newest available products (*"Recién llegados"*), trust stats, location & contact (`#contacto`), and `LocalBusiness` JSON-LD. |
| `/tienda/` | `storefront:catalog` | Public (200 OK) | Public Marketplace Catalog with search (`?q=`), condition (`?estado=` / `?condition=`), price (`?precio=` / `?price=`), sort (`?orden=` / `?sort=`), category (`?category=`), and pagination (`?page=`). |
| `/tienda/categoria/<slug:category_slug>/` | `storefront:category` | Public (200 OK / 404) | SEO-indexable category catalog view filtered by one of the 12 official categories; accepts the same query params as `/tienda/`. |
| `/tienda/producto/<slug:slug>-<int:pk>/` | `storefront:product_detail` | Public (200 OK / 301 / 404) | Public Product Detail page for products in `Product.objects.public_visible()`. Returns a **301 permanent redirect** to the canonical URL if `slug` does not match `product.slug`. |
| `/como-comprar/` | `storefront:how_to_buy` | Public (200 OK) | Standalone shareable page with the *"Saber más / ¿Cómo comprar?"* guide (WhatsApp 24h reservations, free Alfafar pickup, Wallapop/Vinted shipping, payments). |
| `/go/whatsapp/` | `storefront:go_whatsapp` | Public (302 Redirect) | Redirects to the general store WhatsApp (`https://wa.me/<phone>?text=...`) for landing page & header CTAs. |
| `/go/whatsapp/<int:pk>/` | `storefront:go_whatsapp_product` | Public (302 Redirect) | Atomically increments `product.whatsapp_clicks` (`F("whatsapp_clicks") + 1`) and redirects to `https://wa.me/<phone>?text=<encoded_msg>`. |
| `/go/link/<int:link_pk>/` | `storefront:go_listing` | Public (302 Redirect) | Atomically increments `link.clicks_count` (`F("clicks_count") + 1`) for active `ProductListingLink` and redirects to `link.url`. |
| `/aviso-legal/` | `storefront:legal_notice` | Public (200 OK) | Standard LSSI-CE Legal Notice tailored to Rápido Pack (Alfafar, Valencia). |
| `/privacidad/` | `storefront:privacy` | Public (200 OK) | Standard RGPD Privacy Policy tailored to Rápido Pack. |
| `/cookies/` | `storefront:cookies` | Public (200 OK) | Technical Cookies Policy (no third-party tracking cookies in Phase 1). |
| `/sitemap.xml` | `storefront:sitemap` | Public (`application/xml`) | Dynamic XML sitemap listing `/`, `/tienda/`, all 12 `/tienda/categoria/<slug>/` URLs, all `public_visible()` `/tienda/producto/<slug>-<pk>/` URLs, `/como-comprar/`, and legal pages. |
| `/robots.txt` | `storefront:robots` | Public (`text/plain`) | Allows `/`, `/tienda/`; disallows `/admin/`, `/panel/`, `/dashboard/`, `/intake/`, `/products/`, `/login/`, `/api/`, `/go/`. |
| `/panel/` | `inventory:root` | Public $\to$ 302 Redirect | Role-based staff router (`name="root"` preserved): unauthenticated $\to$ `/login/`, Assistant $\to$ `/intake/`, Manager $\to$ `/dashboard/`. |
| `/dashboard/`, `/intake/`, `/products/<int:pk>/` | `inventory:*` | `@login_required` | Unchanged internal operations. |

---

## 5. Data Model & AI Taxonomy Specification

### 5.1 Official 12 Categories (`Category` Model)
Pre-populated via data migration in `inventory`:
1. `motor-y-accesorios` — **Motor y accesorios** (Icon: `two_wheeler`)
2. `moda-y-accesorios` — **Moda y accesorios** (Icon: `apparel`)
3. `tecnologia-y-electronica` — **Tecnología y electrónica** (Icon: `devices`)
4. `deporte-y-ocio` — **Deporte y ocio** (Icon: `fitness_center`)
5. `bicicletas` — **Bicicletas** (Icon: `pedal_bike`)
6. `hogar-y-jardin` — **Hogar y jardín** (Icon: `chair`)
7. `electrodomesticos` — **Electrodomésticos** (Icon: `kitchen`)
8. `cine-libros-y-musica` — **Cine, libros y música** (Icon: `menu_book`)
9. `ninos-y-bebes` — **Niños y bebés** (Icon: `child_friendly`)
10. `coleccionismo` — **Coleccionismo** (Icon: `auto_awesome`)
11. `construccion-y-reformas` — **Construcción y reformas** (Icon: `construction`)
12. `industria-y-agricultura` — **Industria y agricultura** (Icon: `agriculture`)

### 5.2 Official 4 Condition States (`ProductCondition` TextChoices)
- `new_with_tags` — `_("Nuevo con etiquetas")` / `_("New with tags")`
- `very_good` — `_("Muy bueno")` / `_("Very good")`
- `good` — `_("Buen estado")` / `_("Good condition")`
- `vintage` — `_("Vintage")` / `_("Vintage")`

### 5.3 `StorefrontConfiguration` Singleton Model
Editable from Django Admin and Manager settings without code changes:
- `store_name`: default `"Rápido Pack"`
- `store_domain`: default `"rapidopack.es"`
- `tagline_es`: default `"Tu tienda de segunda mano y oportunidad en Alfafar (Valencia) y online"`
- `tagline_en`: default `"Your curated secondhand & opportunity store in Alfafar (Valencia) and online"`
- `whatsapp_number`: default `"34600000000"` (digits only or E.164 cleaned automatically when building `wa.me` links)
- `store_address`: default `"Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia"`
- `maps_url`: default `"https://maps.google.com/?q=Carrer+del+Comte+Ronr%C3%A9e+8+Alfafar"`
- `opening_hours_es`: default `"Lunes a Viernes de 9:30 a 20:00 h · Sábados de 10:00 a 15:00 h"`
- `opening_hours_en`: default `"Mon–Fri 9:30–20:00 · Sat 10:00–15:00"`
- `contact_email`: default `"info@rapidopack.es"`
- `company_nif`: blankable field for legal notice completion

### 5.4 New Fields on `Product` and `ProductListingLink`
On `Product`:
- `category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")`
- `condition = models.CharField(max_length=30, choices=ProductCondition.choices, blank=True, default="", db_index=True)`
- `is_public = models.BooleanField(default=True, db_index=True, verbose_name=_("Visible in Public Storefront"))`
- `is_featured = models.BooleanField(default=False, db_index=True, verbose_name=_("Featured (⭐)"))`
- `is_reserved = models.BooleanField(default=False, db_index=True, verbose_name=_("Reserved (⏳)"))`
- `reserved_until = models.DateTimeField(null=True, blank=True, verbose_name=_("Reserved Until"))`
- `views_count = models.PositiveIntegerField(default=0, verbose_name=_("Public Views"))`
- `whatsapp_clicks = models.PositiveIntegerField(default=0, verbose_name=_("WhatsApp Clicks"))`
- Helper properties:
  - `public_reference`: returns `f"Ref. #{self.pk:04d}"` (e.g., `Ref. #0042` or `Ref. #1042`)
  - `slug`: returns `slugify(self.ai_title or f"producto-{self.pk}")[:80] or f"producto-{self.pk}"`
  - `get_public_url()`: returns `reverse("storefront:product_detail", kwargs={"slug": self.slug, "pk": self.pk})`

On `ProductListingLink`:
- `clicks_count = models.PositiveIntegerField(default=0, verbose_name=_("Outbound Clicks"))`

### 5.5 Public Visibility QuerySet (`ProductQuerySet.public_visible()`)
```python
def public_visible(self):
    seven_days_ago = timezone.now() - timedelta(days=7)
    return (
        self.filter(is_public=True, sale_price__gt=Decimal("0.00"))
        .exclude(ai_title="")
        .filter(
            models.Q(status__in=[ProductStatus.READY, ProductStatus.PUBLISHED], is_sold=False)
            | models.Q(status=ProductStatus.SOLD, is_sold=True, sold_at__gte=seven_days_ago)
        )
    )
```
Ordering in the public catalog always places active items (`is_sold=False`) before recently sold social-proof items (`is_sold=True` at the end of the catalog):
- Default (`sort=newest`): `OrderBy("is_sold", "-is_featured", "-created_at")`
- Featured (`sort=featured`): `OrderBy("is_sold", "-is_featured", "-created_at")`
- Price Low to High (`sort=price_asc`): `OrderBy("is_sold", "sale_price", "-created_at")`
- Price High to Low (`sort=price_desc`): `OrderBy("is_sold", "-sale_price", "-created_at")`

---

## 6. Code Style & Example Snippet

```python
# storefront/views.py
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from inventory.models import Category, Product, ProductImage, ProductListingLink

PUBLIC_PAGE_SIZE = 20
SAFE_PUBLIC_PRODUCT_FIELDS = (
    "id",
    "ai_title",
    "ai_description",
    "sale_price",
    "estimated_retail_price",
    "status",
    "is_sold",
    "sold_at",
    "is_public",
    "is_featured",
    "is_reserved",
    "reserved_until",
    "category_id",
    "condition",
    "views_count",
    "created_at",
    "updated_at",
)

def catalog_view(request):
    qs = (
        Product.objects.public_visible()
        .select_related("category")
        .only(*SAFE_PUBLIC_PRODUCT_FIELDS, "category__id", "category__name", "category__slug", "category__icon")
        .prefetch_related(
            Prefetch("images", queryset=ProductImage.objects.order_by("order", "id")),
            Prefetch(
                "listing_links",
                queryset=ProductListingLink.objects.filter(is_active=True).select_related("site").order_by("site__order"),
            ),
        )
    )
    # Apply category, price range, condition, search, and sorting...
```

---

## 7. Testing Strategy

Automated test suite in [`tests/test_storefront.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_storefront.py) + existing 162+ tests:
1. **`public_visible()` Business Rules:**
   - Excludes `DRAFT`, `PRICE_PENDING`, `AWAITING_INFO`, `BLOCKED`, `is_public=False`, `sale_price=0/None`, and empty `ai_title`.
   - Includes `READY` and `PUBLISHED` (`is_sold=False`).
   - Includes `SOLD` with `sold_at` within the last 7 days, pinned after available items; automatically hides `SOLD` items where `sold_at < now - 7 days`.
2. **Security & Data Firewall (`test_public_storefront_never_leaks_internal_notes_or_clarifications`):**
   - Creates a product with distinctive secret strings in `raw_note`, `ProductClarification.question`/`answer`, and `created_by.username`.
   - Asserts those strings NEVER appear in `/`, `/p/<slug>-<pk>/`, OpenGraph tags, JSON-LD, or `/sitemap.xml`.
3. **Catalog Filtering & Sorting:**
   - Tests filtering by `category` slug, `condition` (`new_with_tags`, `very_good`, `good`, `vintage`), price ranges (`lt_20`, `20_50`, `gt_50`, `min_price`/`max_price`), keyword search (`q`), and sort orders (`newest`, `featured`, `price_asc`, `price_desc`).
4. **Product States & Conversion CTAs:**
   - Available item renders WhatsApp CTA and active Wallapop/Vinted links.
   - `is_reserved=True` item renders `"RESERVADO"` badge and disables primary purchase CTA.
   - Recently `SOLD` item renders `"VENDIDO"` badge and social proof state.
5. **Click Tracking Redirects:**
   - `/go/whatsapp/<pk>/` increments `product.whatsapp_clicks` and redirects to `https://wa.me/<configured_number>?text=...` containing product title, `Ref. #<pk>`, price, and canonical URL.
   - `/go/link/<link_pk>/` increments `link.clicks_count` and redirects to `link.url`.
6. **SEO, Sitemap, Robots & Legal Pages:**
   - Asserts OpenGraph meta tags and valid `Schema.org/Product` JSON-LD on product detail.
   - Asserts `/robots.txt` disallows `/admin/`, `/dashboard/`, `/intake/`.
   - Asserts `/sitemap.xml` includes only `public_visible()` products.
   - Asserts `/legal/aviso-legal/`, `/legal/privacidad/`, `/legal/cookies/` return HTTP 200 with Rápido Pack Alfafar details.
7. **AI Taxonomy Auto-Classification:**
   - Tests that `generate_product_listing` maps `category_slug` and `condition` returned by Gemini onto `Product.category` and `Product.condition`.

---

## 8. Boundaries

### Always Do
- Enforce the strict internal data firewall: never pass `raw_note`, `clarifications`, `created_by`, or `status_logs` to public templates.
- Keep `/dashboard/`, `/intake/`, `/products/<pk>/`, `/manifest.json`, `/sw.js`, and Web Push endpoints 100% functional and backwards-compatible.
- Use the Stitch design system (`Outfit` + `Hanken Grotesk`, Primary Teal `#005c55` / `#0f766e`, Secondary Amber `#904d00` / `#F59E0B`, WhatsApp `#25D366`) in `base_public.html`.
- Keep all UI strings bilingual (`es` / `en`) using Django i18n (`{% trans %}` / `gettext_lazy`) while rendering product titles/descriptions as stored.
- Run `ruff check .` and `python manage.py test` before every commit on `feature/marketplace-storefront`.

### Ask First
- Adding any new third-party Python package to `requirements.txt`.
- Changing the 12 official categories or 4 official condition states confirmed by the client.
- Introducing any public POST form that stores unauthenticated user input.

### Never Do
- Never leak `raw_note` or internal clarifications on any public route.
- Never implement Phase 2 payment gateway / shopping cart checkout logic in Phase 1 (only include the Phase 2 readiness hooks: `is_reserved`, `reserved_until`, `_purchase_box.html`).
- Never commit secrets or `.env` files.

---

## 9. Success Criteria

1. Visiting `/` as an anonymous visitor renders the Rápido Pack marketplace homepage matching the Stitch reference layout (sticky announcement bar with Alfafar address/hours, search bar, ES/EN switcher, compact trust hero, 12-category horizontal rail, price/condition/sort toolbar, 4-col desktop / 2-col mobile grid, Alfafar store map banner, and 3-column footer).
2. Visiting `/` as an authenticated Assistant or Manager additionally shows a floating staff bar with one-click navigation to `/dashboard/`, `/intake/`, and `/admin/`.
3. Visiting `/p/<slug>-<pk>/` renders the 60/40 product detail page with multi-photo WebP thumbnail switcher, zoom lightbox, verification card, sticky `_purchase_box.html`, *"Saber más"* modal, OpenGraph tags, and `Schema.org/Product` JSON-LD.
4. Managers can edit `category`, `condition`, `is_public`, `is_featured`, and `is_reserved` in the staging view (`/products/<pk>/`) and Django Admin, see outbound click counters (WhatsApp vs. Wallapop/Vinted), and configure the store's WhatsApp number in `StorefrontConfiguration`.
5. Clicking "Generate with AI" (`generate_ai_view`) automatically populates `ai_title`, `ai_description`, `category`, and `condition`.
6. All existing tests + the new `test_storefront.py` suite pass (`python manage.py test`) and `ruff check .` reports 0 errors.

---

## 10. Open Questions & Assumptions for Review (Approved)

All client and developer questionnaire items in [`docs/questionnaires/`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/questionnaires/) and the three technical decisions below are 100% confirmed:

1. **Staff Root Redirect (`inventory:root`) vs Public Homepage (`/`):**
   - **Approved:** `/` serves the public marketplace catalog (`storefront:catalog`, returning `HTTP 200` for everyone and showing a staff shortcut bar when logged in); `inventory:root` (`root_redirect_view`) moves to `/staff/` (and `test_root_redirect_*` in `tests/test_auth.py` is updated accordingly).
2. **Default Language on Public Storefront:**
   - **Approved:** Set `LANGUAGE_CODE = 'es'` as the default fallback in `config/settings.py` (since Rápido Pack is based in Valencia, Spain), while keeping full `Accept-Language` negotiation and `/i18n/setlang/` support.
3. **Backfill Command for Existing Products:**
   - **Approved:** Include management command `python manage.py classify_products` (with `--use-ai` and heuristic keyword fallback) so existing staged/seeded products immediately get assigned one of the 12 categories and 4 condition states.
