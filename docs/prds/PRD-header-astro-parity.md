# Spec: Storefront Top Bar & Logo Parity with `rapidopackvalencia.es`

## 1. Objective
Make the Django public storefront top navigation bar (`storefront/templates/storefront/base_public.html`) visually and structurally identical to the Astro corporate site at **`https://rapidopackvalencia.es`**, including the official **Rápido Pack Valencia** logo (`logo-rapido-pack-valencia.png`), so visitors navigating between the Astro pages (`Inicio`, `Paquetería`, `Contacto`) and the Django Store Shelf (`Outlet`) feel they never left the same website.

### Target User & Value
- **Local & online shoppers** clicking **Outlet** from `rapidopackvalencia.es` (or landing directly on `/` or `/tienda/`): experience seamless continuity — zero jarring layout shift, identical brand logo, identical navigation items (`INICIO`, `PAQUETERÍA`, `OUTLET`, `CONTACTO`), identical telephone pill (`640 39 74 34`), live store status indicator (`Abierto ahora · Hasta 20:00` / closed outside hours), and identical mobile `<details>` hamburger drawer.
- **Internal staff (`inventory/`):** Unaffected; internal staff routes (`/panel/`, `/dashboard/`, `/intake/`, `/products/<pk>/`) retain their existing `inventory/templates/inventory/base.html` and the compact Staff Quick Bar when logged in on public pages.

---

## 2. Tech Stack
- **Backend:** Python 3.13+, Django 5.x (`storefront/` app only; `inventory/` untouched)
- **Templates & Styling:** Django Templates + Tailwind CSS CDN (`#tailwind-config` extended with `rapidopackvalencia.es` tokens: `--color-primary: #059652`, `--color-primary-hover: #047842`, `--color-mint-wash: #ecfdf5`, `--color-surface-alt: #f4f6f8`, `--color-surface-dark: #111820`, `--color-border-subtle: #e2e8f0`)
- **Typography:** Google Fonts (`Outfit`, `Plus Jakarta Sans`, `JetBrains Mono`, `Material Symbols Outlined`)
- **Static Asset:** Official logo copied from `https://rapidopackvalencia.es/logo-rapido-pack-valencia.png` (`916×641` transparent PNG) into `storefront/static/storefront/img/logo-rapido-pack-valencia.png` (or `inventory/static/img/storefront/logo-rapido-pack-valencia.png`)

---

## 3. Commands
```powershell
# Lint check
.venv\Scripts\ruff.exe check .

# Django system & migration checks
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

# Compile Spanish/English translation catalogs
.venv\Scripts\python.exe manage.py compile_locales

# Run full automated test suite (634 tests, including Playwright browser & OPPO A74 checks)
.venv\Scripts\python.exe manage.py test

# Local preview server
.venv\Scripts\python.exe manage.py runserver
```

---

## 4. Project Structure
```text
storefront/
  context_processors.py                 # Exposes astro_landing_url, phone display/href, opening status metadata
  static/storefront/img/
    logo-rapido-pack-valencia.png       # Official 916x641 transparent PNG logo from rapidopackvalencia.es
  templates/storefront/
    base_public.html                    # Pixel-parity Astro header (<header> + mobile <details> drawer)
locale/
  es/LC_MESSAGES/django.po|.mo          # Updated Spanish catalog
  en/LC_MESSAGES/django.po|.mo          # Updated English catalog
tests/
  test_storefront.py                    # Header links, logo img, phone pill, active OUTLET state
  test_i18n.py                          # Bilingual ES/EN header strings
  test_oppo_a74_responsive.py           # 360x800 & 320x711 zero horizontal overflow checks
  test_browser_phase39_workflow.py      # Accessibility & skip-link/WhatsApp contrast checks
  test_browser_daily_workflow.py        # End-to-end public storefront workflow checks
```

---

## 5. Code Style & Reference Markup
The Django `<header>` mirrors `rapidopackvalencia.es`'s `<header>` structure and responsive breakpoints:

```html
<header class="sticky top-0 left-0 right-0 w-full z-40 bg-white/95 backdrop-blur-md border-t-[3px] border-t-primary border-b border-border-subtle shadow-[0_10px_30px_-14px_rgba(17,24,32,0.12)]">
  <div class="h-28 sm:h-32 lg:h-36 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4 lg:gap-6">
    <!-- Left: Official Logo + XL Live Status Pill -->
    <div class="flex items-center gap-5 min-w-0">
      <a href="{{ astro_landing_url }}/" aria-label="Rápido Pack Valencia — Ir a Inicio"
         class="flex items-center gap-3 group focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary rounded-md py-1 shrink-0">
        <img src="{% static 'storefront/img/logo-rapido-pack-valencia.png' %}"
             alt="Rápido Pack Valencia" width="172" height="120" fetchpriority="high"
             class="h-[96px] sm:h-[108px] lg:h-[120px] w-auto object-contain transition-transform duration-200 group-hover:scale-[1.02]">
      </a>
      <div id="header-live-status" class="hidden xl:inline-flex items-center gap-2 pl-5 border-l border-border-subtle text-xs font-mono font-medium text-outline whitespace-nowrap">
        <span data-status-dot class="w-2 h-2 rounded-full bg-primary ring-4 ring-primary/15 shrink-0"></span>
        <span data-status-text>{{ store_status_label }}</span>
      </div>
    </div>

    <!-- Center: Desktop Nav (INICIO | PAQUETERÍA | OUTLET [active] | CONTACTO) -->
    <nav aria-label="{% trans 'Main navigation' %}" class="hidden md:flex items-center gap-1.5 lg:gap-2.5 whitespace-nowrap">
      <!-- Active pill for OUTLET: bg-mint-wash text-primary-hover border border-primary/25 shadow-2xs -->
    </nav>

    <!-- Right: Telephone Pill (640 39 74 34) + Mobile <details> Hamburger Drawer -->
  </div>
</header>
```

---

## 6. Testing Strategy
- **Unit & Integration (`tests/test_storefront.py`, `tests/test_i18n.py`):** Verify logo `<img>` renders (`logo-rapido-pack-valencia.png`), navigation links match `INICIO` / `PAQUETERÍA` / `OUTLET` (with `aria-current="page"`) / `CONTACTO`, telephone `640 39 74 34` renders, and ES/EN translations work cleanly.
- **Accessibility & Contrast (`tests/test_ui_accessibility.py`, `tests/test_browser_phase39_workflow.py`):** Verify skip-to-main-content focus, no sub-12px micro-fonts (`text-[10px]` / `text-[11px]`), WCAG AA/AAA contrast, and clean native `<details>` keyboard toggle on mobile.
- **Responsive Mobile (`tests/test_oppo_a74_responsive.py`):** Verify `scrollWidth <= clientWidth` across `360×800` and `320×711` viewports (closed and open mobile drawer).
- **Live Browser Verification:** Inspect desktop (`1440×900`) and mobile (`360×800`) side-by-side against `https://rapidopackvalencia.es` screenshots (`0` console errors, `naturalWidth > 0` for the logo).

---

## 7. Boundaries
- **Always:**
  - Keep `inventory/` (models, views, forms, URLs, admin, internal templates) 100% untouched.
  - Self-host the logo image inside static files (never hotlink to external runtime assets that could break offline/tests).
  - Run `ruff check .`, `manage.py check`, `manage.py compile_locales`, and the full `manage.py test` suite before wrapping up.
- **Ask First:**
  - Whether to keep/relocate the `ES | EN` language switcher and `How to buy` / `WhatsApp` header buttons inside the mobile drawer / top bar vs. keeping the header strictly identical to `rapidopackvalencia.es` (see Open Questions below).
  - Merging into `master` (always requires explicit user approval per `AGENTS.md`).
- **Never:**
  - Remove or weaken existing accessibility checks (`text-[10px]`/`text-[11px]` ban, skip link, `#main-content`, `text-scale`).
  - Commit `.env`, secrets, or temporary SQLite databases.

---

## 8. Success Criteria
1. Desktop (`1440×900`) and tablet (`768px–1280px`) top bar matches `rapidopackvalencia.es` in height (`144px` on `lg:`, `128px` on `sm:`, `112px` on `<640px`), `3px` `#059652` top border, official **Rápido Pack Valencia** `<img>` logo (`916×641` source), `INICIO` / `PAQUETERÍA` / `OUTLET` (active mint pill) / `CONTACTO` navigation, `xl:` live status indicator, and `640 39 74 34` telephone pill.
2. Mobile (`360×800` and `320×711`) renders the official logo + `<details>` hamburger button cleanly with zero horizontal overflow (`scrollWidth <= clientWidth`), and opening the drawer reveals the exact `rapidopackvalencia.es` mobile card (`Abierto ahora...`, `INICIO`, `PAQUETERÍA`, `OUTLET` active, `CONTACTO`, `640 39 74 34`, `Cómo llegar al local`).
3. Switching between `https://rapidopackvalencia.es/` and the Django Store Shelf shows zero visual jump in header height, logo placement, nav links, or color tokens.
4. All automated tests (`manage.py test`), `manage.py check`, `compile_locales`, and `ruff check .` pass with zero errors.

---

## 9. Assumptions & Open Questions (Human Confirmation Required)

### Assumptions Made
1. The official logo (`https://rapidopackvalencia.es/logo-rapido-pack-valencia.png`) should be downloaded once and bundled locally in our Django static files so it loads reliably offline and in CI/Playwright tests.
2. The active top-level navigation item on the Store Shelf is **`OUTLET`** (`aria-current="page"` with the mint wash pill), while **`INICIO`**, **`PAQUETERÍA`**, **`CONTACTO`**, and clicking the **Logo** point back to `https://rapidopackvalencia.es/...` (`/` for Inicio & Logo, `/paqueteria`, `/contacto`) so navigation behaves identically to the Astro site.
3. On `1440px` / `xl:` screens, the live status indicator (`Abierto ahora · Hasta 20:00` / closed outside store hours based on `Europe/Madrid` time: Mon–Fri `09:30–20:00`, Sat `10:00–15:00`) matches `rapidopackvalencia.es`.

### Open Questions
1. **Header Controls (`WhatsApp`, `ES | EN` Language Switcher, `Cómo comprar`):**
   - On `rapidopackvalencia.es`, the right side of the desktop header ONLY has the `640 39 74 34` phone pill (zero WhatsApp button, zero `ES | EN` toggle, zero `Cómo comprar` button in the header — keeping the bar identical).
   - Meanwhile, our Django storefront currently places `ES | EN`, `Cómo comprar`, and a green `WhatsApp` button in the top bar (and `tests/test_browser_daily_workflow.py`, `tests/test_browser_phase39_workflow.py`, and `tests/test_ui_accessibility.py` look for those in the page).
   - **Recommended Option:** Make the top bar **100% identical to `rapidopackvalencia.es`** (Logo + Live Status + `INICIO / PAQUETERÍA / OUTLET / CONTACTO` + `640 39 74 34` phone pill on desktop, and the exact `<details>` drawer on mobile), and move the `ES | EN` language switcher cleanly into the **footer** (and/or inside the mobile drawer bottom) while keeping `Cómo comprar` and `WhatsApp` in the Store Shelf editorial header & Section `02` (updating the header-specific test assertions accordingly)? Or do you want `ES | EN` / `WhatsApp` kept subtly in the top bar?
2. **Header Sticky vs. Fixed & Height (`144px` on Desktop):**
   - `rapidopackvalencia.es` uses `fixed top-0` with `h-28 sm:h-32 lg:h-36` (`112px` / `128px` / `144px`). Notice when a staff user is logged in, our top bar also shows the compact Staff Quick Bar (`Staff Mode`). Using `sticky top-0` (instead of `fixed top-0`) keeps the exact same visual pinning while preventing the Staff Quick Bar or page content from being covered underneath!
