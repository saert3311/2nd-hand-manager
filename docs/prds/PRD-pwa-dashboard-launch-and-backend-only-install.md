# PRD: PWA Dashboard Launch & Backend-Only Installability — Phase 58

## 1. Objective

### Problem Statement
When the public marketplace storefront (`storefront` app) took over the root path `/` (`storefront:home`), the existing PWA Web App Manifest (`manifest_view` in `inventory/views.py`) retained `"start_url": "/"` and `"scope": "/"`. Meanwhile, `inventory/templates/inventory/base.html` continued rendering `<link rel="manifest">`, iOS standalone meta tags (`apple-mobile-web-app-capable`), and root Service Worker registration (`/sw.js`) unconditionally across every internal template—including the unauthenticated `/login/` page. In addition, fallback notification click URLs in `inventory/templates/inventory/sw.js` and `inventory/services/push_service.py` still default to `"/"`.

As a result:
1. Launching the installed PWA opens the public storefront (`/`) instead of the staff staging dashboard (`/dashboard/`).
2. PWA installability metadata (`<link rel="manifest">` and standalone tags) and Service Worker registration are exposed outside the authenticated dashboard workflow (e.g., on `/login/` and sibling staff pages), increasing the risk of prompting non-dashboard users or associating installability outside `/dashboard/`.

### Target Users & Scope
- **Target Users:** All authenticated backend staff users (**Store Managers** and **Sourcing Assistants**) accessing `/dashboard/` (`inventory:dashboard`).
- **In Scope:**
  - Update `/manifest.json` (`manifest_view` in `inventory/views.py`) to set `"start_url": "/dashboard/"`, declare an explicit stable `"id": "/dashboard/"`, and keep `"scope": "/"` so navigating between `/dashboard/` and sibling backend routes (`/intake/`, `/products/<pk>/`, `/pallets/`) stays inside standalone PWA mode without showing an in-app browser toolbar.
  - Emit `<link rel="manifest" href="{% url 'inventory:manifest' %}">` and iOS standalone install meta tags (`apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title`) **strictly on `/dashboard/` for authenticated users** via a dedicated template block (`{% block pwa_install_head %}`) defined empty in `inventory/templates/inventory/base.html` and populated in `inventory/templates/inventory/dashboard.html`.
  - Rely exclusively on the **browser's native install prompt** (no custom in-page "Install App" button UI).
  - Ensure **zero** PWA manifest links, standalone meta tags, or Service Worker registration on all public storefront pages (`storefront/templates/storefront/base_public.html` and its child templates: `/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) for both anonymous and authenticated users, as well as on unauthenticated `/login/`.
  - Gate Service Worker (`/sw.js`) registration and App Badging API synchronization (`navigator.setAppBadge` / `clearAppBadge`) in `inventory/templates/inventory/base.html` behind `{% if user.is_authenticated %}` so Web Push Notifications (`🔔 Enable Alerts`) continue functioning across `/dashboard/`, `/intake/`, `/products/<pk>/`, and `/pallets/`, while anonymous visitors on `/login/` never register `/sw.js`.
  - Add `target="_blank" rel="noopener noreferrer"` to the internal navbar and mobile-drawer **Storefront** links in `inventory/templates/inventory/base.html` (desktop nav link and `#mobile-link-storefront`) so opening the public catalog from inside an installed standalone PWA launches a regular browser tab instead of navigating the standalone PWA window into the public storefront.
  - Update default fallback push notification URLs in `inventory/templates/inventory/sw.js` and `inventory/services/push_service.py` from `"/"` to `"/dashboard/"`.
- **Out of Scope:**
  - Custom in-dashboard "Install App" button or custom prompt banners.
  - Database schema migrations or new models.
  - Changing `CustomLoginView.get_success_url()` role-based post-login redirects (`Assistants` → `/intake/`, `Managers` → `/dashboard/`).
  - Restricting `/manifest.json` HTTP responses behind `@login_required` (browsers fetch linked manifests without cookies by default, so `/manifest.json` must remain HTTP `200 OK` JSON without auth redirects; installability is gated by only rendering `<link rel="manifest">` on authenticated `/dashboard/`).
  - Modifying `storefront/` runtime views or templates.

---

## 2. Tech Stack & Architectural Invariants

- **Language & Framework:** Python 3.13+, Django 5.x (`inventory` and `storefront` apps)
- **Templates & Frontend:** Django Templates, Tailwind CSS, Vanilla JavaScript, W3C Web App Manifest (`application/manifest+json`), Service Worker API (`/sw.js`), Web Push API (`pywebpush`)
- **Zero Caching Service Worker Policy:** `/sw.js` remains a strict pass-through `fetch` handler (no caching of HTML responses or Django CSRF tokens).
- **Database & Dependencies:** Zero schema migrations; zero new Python or JS dependencies.
- **Internationalization (i18n):** Zero new user-facing UI strings introduced; verify existing ES/EN catalogs remain compiled and passing.
- **Viewport & Layout Invariance:** No new visible UI controls added; preserves OPPO A74 (`360×800` and `320×711`) zero horizontal overflow (`scrollWidth <= clientWidth`) and WCAG 2.1 AA contrast guarantees.

---

## 3. Commands

Always run project commands via the workspace virtual environment (`.venv\Scripts\...`):

```powershell
# Lint & style check (Ruff)
.venv\Scripts\ruff.exe check .

# Django system check
.venv\Scripts\python.exe manage.py check

# Compile bilingual translation catalogs (.po -> .mo via polib)
.venv\Scripts\python.exe manage.py compile_locales

# Run targeted PWA, auth, and storefront tests
.venv\Scripts\python.exe manage.py test tests.test_pwa_push tests.test_storefront tests.test_auth -v 2

# Run full automated test suite
.venv\Scripts\python.exe manage.py test

# Start local development server
.venv\Scripts\python.exe manage.py runserver
```

---

## 4. Project Structure (Files Affected)

| File | Role in Phase 58 |
|---|---|
| `inventory/views.py` | Update `manifest_view`: add explicit `"id": "/dashboard/"`, change `"start_url": "/dashboard/"`, and preserve `"scope": "/"`. |
| `inventory/templates/inventory/base.html` | Replace inline `<link rel="manifest">` and `apple-mobile-web-app-*` standalone meta tags with empty `{% block pwa_install_head %}{% endblock %}`; gate `/sw.js` registration and `setAppBadge`/`clearAppBadge` behind `{% if user.is_authenticated %}`; add `target="_blank" rel="noopener noreferrer"` to desktop and mobile (`#mobile-link-storefront`) Storefront navigation links. |
| `inventory/templates/inventory/dashboard.html` | Override `{% block pwa_install_head %}` (guarded by `{% if user.is_authenticated %}`) to emit `<link rel="manifest" href="{% url 'inventory:manifest' %}">` and iOS standalone meta tags (`apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title`). |
| `inventory/templates/inventory/sw.js` | Update default fallback notification `url` and `notificationclick` `targetPath` from `'/'` to `'/dashboard/'`. |
| `inventory/services/push_service.py` | Update default `url: str = "/dashboard/"` parameter and fallback `url or "/dashboard/"` in `send_push_to_subscription`, `send_push_to_user`, and `send_push_to_group`. |
| `tests/test_pwa_push.py` | Update existing manifest (`start_url`, `id`, `scope`) and `/intake/` template assertions; add automated view, role, and Playwright E2E tests covering the full surface isolation matrix, Storefront link `target="_blank"` attributes, and default push fallback URLs. |
| `verify_workday_all_cases.py` | Optional alignment check if manual verification script inspects `manifest.json` `start_url` (confirm during Phase 2/4). |

---

## 5. Detailed Functional & Non-Functional Requirements

### 5.1 Web App Manifest Contract (`/manifest.json`)
- `GET /manifest.json` (`inventory:manifest`) returns HTTP `200 OK` with `Content-Type: application/manifest+json` without requiring login cookies (standard browser manifest fetches omit credentials).
- Required manifest fields:
  - `"id": "/dashboard/"` — explicit, stable app identity separate from the origin root.
  - `"start_url": "/dashboard/"` — launches installed PWAs directly into the internal staging dashboard.
  - `"scope": "/"` — retains sibling internal routes (`/intake/`, `/products/<pk>/`, `/pallets/`) within the installed standalone window without triggering an in-app browser URL bar.
  - `"display": "standalone"`, `"orientation": "portrait-primary"`, `"background_color": "#f8fafc"`, `"theme_color": "#059669"`, `icons` (`192x192` and `512x512` `any` + `maskable`), and `shortcuts` (`/intake/`, `/dashboard/`, `/dashboard/?status=awaiting_info`) preserved.
- **Rollout Behavior for Previously Installed Devices:** Staff devices that already installed the PWA while `"start_url": "/"` was active may cache the legacy app identity/start URL until the browser refreshes the manifest or the user performs a one-time uninstall/reinstall from `/dashboard/`.

### 5.2 Strict PWA & Service Worker Surface Matrix

| Surface / Route | User State | `<link rel="manifest">` | Apple Standalone Meta Tags | `/sw.js` Registration | Push Toggle (`🔔`) |
|---|---|---|---|---|---|
| Public Storefront (`/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) | Anonymous | **No** | **No** | **No** | **No** |
| Public Storefront (`/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) | Authenticated Staff | **No** | **No** | **No** | **No** |
| Staff Sign-In (`/login/`) | Anonymous | **No** | **No** | **No** | **No** |
| Staging Dashboard (`/dashboard/`) | Authenticated Manager or Assistant | **Yes** | **Yes** | **Yes** (`scope: '/'`) | **Yes** |
| Other Backend Pages (`/intake/`, `/products/<pk>/`, `/pallets/`) | Authenticated Manager or Assistant | **No** | **No** | **Yes** (`scope: '/'`) | **Yes** |

- Note: Standard non-install metadata (`<meta name="theme-color">`, `<link rel="apple-touch-icon">`, and `<link rel="icon">`) may remain in `inventory/templates/inventory/base.html` for browser tab/bookmark icons without making `/login/`, `/intake/`, `/products/<pk>/`, or `/pallets/` installable.
- Public storefront templates (`storefront/templates/storefront/base_public.html`) remain completely free of manifest links, standalone tags, and Service Worker registration scripts.

### 5.3 Standalone PWA Navigation, Auth Launch & Storefront Escape Hatch
- **Seamless Backend Navigation:** Keeping `"scope": "/"` ensures that moving from `/dashboard/` to `/intake/`, `/products/<pk>/`, or `/pallets/` inside the installed PWA stays inside the standalone window.
- **Signed-Out PWA Launch:** When an unauthenticated staff member opens the installed PWA, the browser requests `/dashboard/`, `@login_required` redirects to `/login/?next=/dashboard/`, and signing in completes the flow. Existing `CustomLoginView.get_success_url()` role-routing behavior remains unchanged.
- **Storefront Escape Hatch (`target="_blank"`):** Both the desktop navbar Storefront link and the mobile drawer Storefront link (`#mobile-link-storefront`) in `inventory/templates/inventory/base.html` include `target="_blank" rel="noopener noreferrer"` so staff tapping Storefront from the installed standalone PWA open the public storefront in an external browser tab instead of navigating the PWA window into the public site.

### 5.4 Push Notification Fallback URL Consistency (`sw.js` & `push_service.py`)
- In `inventory/templates/inventory/sw.js`:
  - Default `payload.url` in the `push` listener changes from `'/'` to `'/dashboard/'`.
  - Fallback `targetPath` in `notificationclick` (when `event.notification.data.url` is absent) changes from `'/'` to `'/dashboard/'`.
- In `inventory/services/push_service.py`:
  - Default `url: str = "/dashboard/"` in `send_push_to_subscription()`, `send_push_to_user()`, and `send_push_to_group()`.
  - Payload fallback `"url": url or "/dashboard/"`.

---

## 6. Code Style

Follow PEP 8, Ruff (`target-version = "py313"`, `line-length = 120`, rules `E, F, I, W`), and Django template conventions:

```python
# inventory/views.py
def manifest_view(request):
    """
    Serves the W3C Web App Manifest (/manifest.json) for PWA installation.
    """
    manifest_data = {
        "id": "/dashboard/",
        "name": "2ndHand Product Intake & Staging Hub",
        "short_name": "2ndHand",
        "description": str(_("Mobile intake & AI staging workspace for second-hand inventory.")),
        "start_url": "/dashboard/",
        "scope": "/",
        "display": "standalone",
        ...
    }
    return JsonResponse(manifest_data, content_type="application/manifest+json")
```

```django
{# inventory/templates/inventory/base.html (<head>) #}
  <!-- PWA Icons & Theme Metadata (install manifest injected only on /dashboard/ for authenticated staff) -->
  {% block pwa_install_head %}{% endblock %}
  <meta name="theme-color" content="#059669">
  <link rel="apple-touch-icon" href="{% static 'inventory/icons/apple-touch-icon.png' %}">
  <link rel="icon" type="image/png" sizes="192x192" href="{% static 'inventory/icons/icon-192.png' %}">

{# inventory/templates/inventory/dashboard.html #}
{% block pwa_install_head %}
{% if user.is_authenticated %}
  <link rel="manifest" href="{% url 'inventory:manifest' %}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="2ndHand">
{% endif %}
{% endblock %}
```

```django
{# inventory/templates/inventory/base.html (body end) #}
  {% if user.is_authenticated %}
  <!-- Authenticated Backend PWA Service Worker Registration & App Badge Sync -->
  <script>
    (function() {
      if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
          navigator.serviceWorker.register("{% url 'inventory:service_worker' %}", { scope: '/' }).catch(function() {});
        });
      }
      ...
    })();
  </script>
  {% endif %}
```

---

## 7. Testing Strategy

- **Framework & Location:** Django `TestCase` and `StaticLiveServerTestCase` (Playwright Chromium) in `tests/test_pwa_push.py`, alongside full regression runs (`tests.test_storefront`, `tests.test_auth`, full suite).
- **Automated Test Coverage Required:**
  1. **Manifest JSON Contract (`PWAManifestAndServiceWorkerTests`):**
     - `GET /manifest.json` returns HTTP `200`, `application/manifest+json`, `"id": "/dashboard/"`, `"start_url": "/dashboard/"`, `"scope": "/"`, `"display": "standalone"`, icons, and shortcuts—accessible without login.
  2. **Service Worker & Push Service Defaults:**
     - `GET /sw.js` defaults `payload.url` and `notificationclick` fallback `targetPath` to `"/dashboard/"`.
     - `push_service.send_push_to_subscription`, `send_push_to_user`, and `send_push_to_group` default `url` to `"/dashboard/"` when omitted.
  3. **Template Surface Isolation Matrix (View Tests):**
     - **Authenticated Manager on `/dashboard/`:** contains `rel="manifest"`, `apple-mobile-web-app-capable`, `navigator.serviceWorker.register`, `#push-toggle-btn`, and Storefront links with `target="_blank"` and `rel="noopener noreferrer"`.
     - **Authenticated Assistant on `/dashboard/`:** contains `rel="manifest"`, `apple-mobile-web-app-capable`, and `navigator.serviceWorker.register`.
     - **Authenticated Staff on `/intake/`, `/products/<pk>/`, and `/pallets/`:** does **not** contain `rel="manifest"` or `apple-mobile-web-app-capable`, while still containing `navigator.serviceWorker.register` and `#push-toggle-btn`.
     - **Anonymous Visitor on `/login/`:** does **not** contain `rel="manifest"`, `apple-mobile-web-app-capable`, or `navigator.serviceWorker.register`.
     - **Public Storefront (`/`, `/tienda/`, `/como-comprar/`) for both Anonymous and Authenticated Staff:** does **not** contain `rel="manifest"`, `apple-mobile-web-app-capable`, or `navigator.serviceWorker.register`.
  4. **Playwright Real-Browser Verification (`BrowserPWAServiceWorkerAndPushTests`):**
     - Anonymous visitor on `/` (`storefront:home`): zero `link[rel="manifest"]` elements and `navigator.serviceWorker.getRegistrations()` length `=== 0`.
     - Anonymous visitor on `/login/`: zero `link[rel="manifest"]` elements and `navigator.serviceWorker.getRegistrations()` length `=== 0`.
     - Authenticated manager on `/dashboard/`: `link[rel="manifest"]` href is `"/manifest.json"` (whose `start_url`, `id`, and `scope` match `/dashboard/` and `/`), `navigator.serviceWorker.ready` scope is `"{live_server_url}/"`, and `#push-toggle-btn` is visible.
     - Navigating to `/intake/` while authenticated: zero `link[rel="manifest"]` elements while `navigator.serviceWorker.ready` scope remains `"{live_server_url}/"` and `#push-toggle-btn` remains visible.
     - Authenticated manager visiting `/` (public storefront): zero `link[rel="manifest"]` elements.

---

## 8. Boundaries

- **Always:**
  - Keep `/sw.js` strictly pass-through (zero HTML or CSRF token caching).
  - Keep `/manifest.json` publicly fetchable (`200 OK` JSON, no auth redirect) while strictly restricting `<link rel="manifest">` emission to authenticated `/dashboard/`.
  - Pass 100% of `.venv\Scripts\ruff.exe check .`, `.venv\Scripts\python.exe manage.py check`, `.venv\Scripts\python.exe manage.py compile_locales`, and `.venv\Scripts\python.exe manage.py test`.
- **Ask First:**
  - Changing `scope` from `"/"` to `"/dashboard/"`.
  - Adding an explicit in-UI "Install App" button or banner.
  - Modifying `CustomLoginView` post-login role redirect logic.
  - Modifying `storefront/` runtime views or templates.
  - Merging into `master` (explicit user approval mandatory per `AGENTS.md`).
- **Never:**
  - Emit `<link rel="manifest">`, `apple-mobile-web-app-capable`, or `navigator.serviceWorker.register` on public storefront pages or unauthenticated `/login/`.
  - Commit `.env`, secrets, or unrelated untracked files (`browser_verification_screenshots/oppo_a74/...`, `file`).
  - Skip, delete, or weaken existing assertions solely to pass tests.

---

## 9. Success Criteria

1. [ ] `GET /manifest.json` returns HTTP `200` (`application/manifest+json`) with `"id": "/dashboard/"`, `"start_url": "/dashboard/"`, and `"scope": "/"`.
2. [ ] Authenticated Managers and Assistants visiting `/dashboard/` receive `<link rel="manifest" href="/manifest.json">`, iOS standalone meta tags, and `/sw.js` registration (`scope: '/'`), using the browser's native install UI only.
3. [ ] Authenticated staff visiting `/intake/`, `/products/<pk>/`, and `/pallets/` receive `/sw.js` registration (preserving Web Push notifications) and **no** `<link rel="manifest">` or `apple-mobile-web-app-capable` tags.
4. [ ] Anonymous visitors on `/login/` and both anonymous and authenticated visitors on all public storefront routes (`/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) receive **zero** `<link rel="manifest">`, **zero** standalone meta tags, and **zero** Service Worker registration.
5. [ ] Internal navbar and mobile drawer Storefront links in `inventory/templates/inventory/base.html` open in a new tab (`target="_blank" rel="noopener noreferrer"`).
6. [ ] Default fallback push notification URLs in `inventory/templates/inventory/sw.js` and `inventory/services/push_service.py` target `"/dashboard/"`.
7. [ ] Automated unit, view, and Playwright browser tests in `tests/test_pwa_push.py` verify every surface rule and pass alongside the full suite (`manage.py test`), `manage.py check`, `manage.py compile_locales`, and `ruff check .` with 0 errors.

---

## 10. Validated Decisions & Open Questions

- **Validated Design Decisions (Confirmed by User):**
  1. **Manifest Scope vs. Route Trade-Off:** Keep `"scope": "/"` while emitting `<link rel="manifest">` strictly on `/dashboard/`, so `/intake/`, `/products/<pk>/`, and `/pallets/` stay inside standalone mode without a browser toolbar and Storefront links open in a new tab (`target="_blank"`).
  2. **Target Surface & Roles:** Emit `<link rel="manifest">` and enable browser installation prompts strictly on `/dashboard/` for all authenticated backend users (**Managers** and **Assistants**).
  3. **Install UX:** Use the browser's native install prompt only (clean UI with no custom in-page install button).
- **Open Questions:** None — all design decisions validated. (Rollout note: any device that previously installed the PWA under the prior `"start_url": "/"` manifest may require a one-time uninstall/reinstall from `/dashboard/` to pick up the new `id` and `start_url`.)
