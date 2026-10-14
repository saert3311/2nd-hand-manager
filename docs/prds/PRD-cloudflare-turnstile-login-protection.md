# Product Requirements Document (PRD): Cloudflare Turnstile Login Protection

## 1. Executive Summary
Integrate **Cloudflare Turnstile** into the authentication login flow (`/login/` / `CustomLoginView`) to safeguard the 2ndHand Staging Hub against automated credential stuffing, bot brute-force attacks, and abusive login attempts. Cloudflare Turnstile provides privacy-preserving, CAPTCHA-free smart challenges that verify human users without frustrating interactive puzzle-solving. When Turnstile is enabled, login submissions require a valid client-side challenge token verified against Cloudflare's server-side API. The feature supports seamless local development and automated CI testing via official Cloudflare dummy keys and graceful configuration gating.

---

## 2. Problem Statement
1. **Public Authentication Attack Surface:** The 2ndHand Staging Hub exposes a public login screen (`/login/`). Without bot protection, malicious actors or automated crawlers can execute high-frequency dictionary attacks or credential stuffing against assistant and manager accounts.
2. **User Experience Deterioration with Traditional CAPTCHAs:** Traditional image/text puzzle CAPTCHAs (e.g. reCAPTCHA v2) create severe friction for mobile warehouse assistants working rapidly in fast-paced retail environments.
3. **Privacy Concerns:** Legacy reCAPTCHA solutions track user browsing behavior across the web. Turnstile provides a privacy-first alternative without cross-site tracking.
4. **Resilience & Testing Isolation:** The authentication pipeline must remain reliable in environments without active Internet access (such as headless CI runners or unit tests) without compromising production security.

---

## 3. User Personas & Scenarios

### Persona: Sourcing Assistant (User A) / Store Manager (User B)
- **Scenario 1 (Normal Human Login):** An assistant or manager visits `/login/`. The Turnstile widget seamlessly and automatically executes a background challenge (or presents a single checkbox if suspicion is elevated). Upon entering username and password, the form submits with the generated `cf-turnstile-response` token. The server validates the token with Cloudflare and logs the user in immediately.
- **Scenario 2 (Expired / Failed Challenge):** If a user leaves the login page open for an extended duration and the token expires, or if verification fails, the login form renders an actionable, localized error message (*"Por favor, complete la verificación de seguridad." / "Please complete the security challenge."*) prompting a retry.

### Persona: Automated Bot / Attacker
- **Scenario 3 (Automated POST without Token):** A bot script sends automated HTTP POST requests directly to `/login/` with username/password dictionaries. The server detects a missing `cf-turnstile-response` token and rejects the authentication attempt immediately, before checking credentials against the database.
- **Scenario 4 (Forged or Replayed Token):** An attacker submits a replayed or spoofed token. The server verifies the token with Cloudflare's `siteverify` endpoint, receives `success: false`, and rejects the attempt.

---

## 4. Scope & Functional Requirements

### 4.1 Client-Side Widget Integration (`inventory/templates/registration/login.html`)
- Load Cloudflare Turnstile JavaScript API:
  `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>` (loaded only when `TURNSTILE_ENABLED` is true).
- Inject Turnstile widget container above the submit button:
  `<div class="cf-turnstile" data-sitekey="{{ TURNSTILE_SITE_KEY }}" data-theme="light"></div>`.
- Widget automatically injects hidden field `cf-turnstile-response` into the login POST payload.
- Full responsive styling matching the clean Tailwind CSS design system.

### 4.2 Server-Side Verification Service (`inventory/services/turnstile_service.py`)
- Dedicated service function `verify_turnstile_token(token: str, remote_ip: Optional[str] = None) -> bool`.
- Sends HTTP POST request to Cloudflare verification API: `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
- Payload parameters:
  - `secret`: Cloudflare Secret Key (`TURNSTILE_SECRET_KEY`).
  - `response`: Client-submitted token (`cf-turnstile-response`).
  - `remoteip`: (Optional) Client IP address from `request.META`.
- Enforces request timeout (default 5.0 seconds) to prevent server hangs during third-party latency.
- Returns `True` on success, `False` on failure, token expiration, or network errors (fail-secure in production).

### 4.3 Form & View Integration (`inventory/forms.py` & `inventory/views.py`)
- Define `TurnstileAuthenticationForm(AuthenticationForm)` in `inventory/forms.py`:
  - Extracts `cf-turnstile-response` from POST data in `clean()`.
  - When `TURNSTILE_ENABLED` is `True`, validates token via `verify_turnstile_token`.
  - Raises `forms.ValidationError` with localized error message if token is missing or verification fails.
- Update `CustomLoginView` in `inventory/views.py`:
  - Uses `authentication_form = TurnstileAuthenticationForm`.
  - Passes `TURNSTILE_SITE_KEY` and `TURNSTILE_ENABLED` in template context.

### 4.4 Environment Configuration & Feature Flagging (`config/settings.py` & `.env.example`)
- Settings variables:
  - `TURNSTILE_SITE_KEY`: Public sitekey from Cloudflare Dashboard.
  - `TURNSTILE_SECRET_KEY`: Private secret key from Cloudflare Dashboard.
  - `TURNSTILE_ENABLED`: Boolean flag. Evaluates to `True` only when explicitly enabled AND both keys are present.
  - `TURNSTILE_TIMEOUT`: Request timeout in seconds (default 5).
- Dev/CI Dummy Keys: Cloudflare's official testing keys:
  - Always passes: Sitekey `1x00000000000000000000AA`, Secret `1x0000000000000000000000000000000AA`.
  - Always fails: Sitekey `2x00000000000000000000AB`, Secret `2x0000000000000000000000000000000AB`.

### 4.5 Internationalization (i18n)
- Localized error messages registered in `locale/es/LC_MESSAGES/django.po`:
  - English: *"Please complete the security challenge."*
  - Spanish: *"Por favor, completa la verificación de seguridad."*
  - English: *"Security verification failed. Please try again."*
  - Spanish: *"Error en la verificación de seguridad. Por favor, inténtalo de nuevo."*

---

## 5. Non-Functional & Security Requirements
1. **Zero Secret Leakage:** Secret key is never rendered in HTML templates or exposed in client bundles.
2. **Safe Failure Mode:** If verification times out or Cloudflare responds with non-200 in production, fail closed (reject authentication) to protect against automated bypass during attacks.
3. **Headless & Test Isolation:** When running automated tests (`python manage.py test` / `IS_TESTING`), mock the Cloudflare HTTP call or bypass if keys are omitted, ensuring the test suite remains fast and decoupled from external network status.
4. **Responsive Performance:** Turnstile challenge loads asynchronously (`async defer`) without degrading First Contentful Paint (FCP) on mobile networks.

---

## 6. Acceptance Criteria
- [ ] Turnstile widget renders correctly on `/login/` when `TURNSTILE_ENABLED=True`.
- [ ] Valid Turnstile token allows successful user authentication for assistants and managers.
- [ ] Missing or invalid Turnstile token rejects login with a clear localized validation error.
- [ ] Turnstile validation can be cleanly disabled for testing/dev environments via `.env` without throwing errors.
- [ ] Comprehensive unit and integration test suite added in `tests/test_turnstile.py` verifying passing tokens, failing tokens, missing tokens, and network timeouts.
- [ ] All 162+ existing automated tests continue to pass with 0 regressions.
