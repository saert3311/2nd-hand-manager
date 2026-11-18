# Cross-Subdomain Cookie Consent & Google Consent Mode v2 Sync (`rapidopackvalencia.es`)

## Problem Statement
How might we replicate the exact `Configurar cookies` (`#footer-cookie-settings-btn`) and `Control de Cookies` dialog experience from `rapidopackvalencia.es` on the Django Store Shelf and synchronize the visitor's `rpv_cookie_consent` decision seamlessly across the root domain (`rapidopackvalencia.es`) and the store subdomain so visitors are only prompted once?

## Recommended Direction
Implement a **shared first-party root-domain cookie (`rpv_cookie_consent`) + `localStorage` fallback + Google Consent Mode v2 (`GTM-PGBXBVXJ`)**, paired with 1:1 UI parity and canonical HTTP 302 legal redirects:

1. **Cross-Subdomain Consent Cookie (`rpv_cookie_consent`)**:
   - Browser `localStorage` is isolated per origin (`https://rapidopackvalencia.es` cannot share `localStorage` with `https://tienda.rapidopackvalencia.es`), whereas a cookie scoped with `Domain=.rapidopackvalencia.es; Path=/; Max-Age=31536000; SameSite=Lax; Secure` is shared natively across `rapidopackvalencia.es` and all `*.rapidopackvalencia.es` subdomains.
   - Local development (`localhost` / `127.0.0.1`) falls back cleanly to a host-only cookie mirrored to `localStorage`.
   - Both Python (`storefront/context_processors.py`) and client JS accept both URL-encoded JSON (`{"essential":true,"analytics":true,"version":1}`) and simple string tokens (`"accepted"` / `"rejected"` / `"granted"` / `"denied"`).

2. **Zero-Flash Server-Side Rendering (`storefront/context_processors.py`)**:
   - `storefront_config(request)` parses `request.COOKIES.get("rpv_cookie_consent")` to inject `cookie_consent_decided` and `cookie_analytics_granted` into every public template.
   - If the visitor already decided on `rapidopackvalencia.es`, the Django Store Shelf renders `#cookie-banner-container` already hidden, pre-checks `#cookie-analytics-toggle` when analytics were accepted, and sets `gtag('consent', 'default', { analytics_storage: 'granted' })` before GTM loads.

3. **1:1 UI Parity (`#footer-cookie-settings-btn` & `#cookie-banner-container`)**:
   - Footer bottom bar includes `#footer-cookie-settings-btn` (`Configurar cookies` / `Configure cookies`), opening `#cookie-banner-container` with `#cookie-settings-panel` expanded.
   - First-time undecided visitors see the floating bottom-right `#cookie-banner-container` (`Control de Cookies` with `Aceptar todas`, `Rechazar`, and `Configurar preferencias`), styled with `>= 12px` typography and full `320px`/`360px` OPPO A74 mobile safety.

4. **Google Consent Mode v2 + GTM (`GTM-PGBXBVXJ`)**:
   - Configures `GTM_CONTAINER_ID` via `config/settings.py` & `.env.example` (defaulting to `GTM-PGBXBVXJ`).
   - Initializes `gtag('consent', 'default', ...)` in `<head>` with `ad_storage`, `ad_user_data`, and `ad_personalization` denied, and `analytics_storage` matched to `cookie_analytics_granted`, followed by both the `<head>` `gtm.js` loader and `<body>` `<noscript>` iframe fallback.
   - Calls `gtag('consent', 'update', { analytics_storage: ... })` immediately on Accept, Reject, or Save Selection.
   - **E-Commerce & Lead `dataLayer` Events**: Pushes `view_item_list` and `search` on catalog views, `view_item` on product detail pages, `how_to_buy_open` when opening the quick guide modal, and delegated `whatsapp_click` / `marketplace_click` lead events (with item ID, title, category, condition, and EUR price).
   - **Staff Exclusion (`gtm_enabled=False`)**: When an authenticated manager or assistant browses the public storefront (`is_staff_member=True`), `gtm.js` and the `<noscript>` iframe are omitted and `traffic_type: 'internal'` is pushed to `dataLayer` so team inspections never pollute visitor analytics.

5. **Canonical Legal Redirects (`/aviso-legal/`, `/privacidad/`, `/cookies/`)**:
   - Storefront legal routes redirect (HTTP 302) directly to `https://rapidopackvalencia.es/{aviso-legal,privacidad,cookies}` and are excluded from `/sitemap.xml` so the main corporate site remains the single source of truth.

---

## Companion Snippet for the Astro Site (`rapidopackvalencia.es`)
Ensure the Astro cookie consent `<script>` sets and clears `rpv_cookie_consent` using `Domain=.rapidopackvalencia.es` on production hosts so decisions made on the root domain are immediately readable by the Django store subdomain:

```js
function getSharedCookieDomain() {
  const host = window.location.hostname.toLowerCase();
  if (host === "rapidopackvalencia.es" || host.endsWith(".rapidopackvalencia.es")) {
    return "; Domain=.rapidopackvalencia.es";
  }
  return "";
}

function writeSharedConsentCookie(valueObj) {
  const encoded = encodeURIComponent(JSON.stringify(valueObj));
  const domainAttr = getSharedCookieDomain();
  const secureAttr = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `rpv_cookie_consent=${encoded}; Path=/; Max-Age=31536000; SameSite=Lax${domainAttr}${secureAttr}`;
  try {
    localStorage.setItem("rpv_cookie_consent", JSON.stringify(valueObj));
  } catch (_) {}
}
```

## Key Assumptions Validated
- [x] Existing Astro cookie name is `rpv_cookie_consent` (1-year TTL, Technical/Mandatory).
- [x] Astro site uses `GTM-PGBXBVXJ` / `G-7S8Z63R6GQ` with Consent Mode v2 (`analytics_storage` toggled; ad storage flags remain `denied`).
- [x] If the Astro site currently writes a host-only `rpv_cookie_consent` cookie without `Domain=.rapidopackvalencia.es`, updating it with the snippet above completes bidirectional sync across both subdomains.

## Not Doing (and Why)
- **Not building a cross-origin hidden iframe `postMessage` bridge** — a first-party root-domain cookie (`Domain=.rapidopackvalencia.es`) is native, synchronous on initial HTTP request, privacy-safe, and works without third-party cookie restrictions.
- **Not duplicating Spanish legal policy text in Django** — redirecting `/aviso-legal/`, `/privacidad/`, and `/cookies/` to `rapidopackvalencia.es` prevents policy drift.
