# Product Requirements Document (PRD) & Specification
# Compilation & Docker Image Build Timestamp Display ("Which Compilation Are We Using?")

## 1. Objective

Provide continuous, unambiguous operational traceability across environments (development, staging, and production) by displaying the **compilation / Docker image build date, time, and version metadata** in the bottom footer of the **2ndHand Staging Hub** application.

### 1.1 Business & Operational Problems Solved

1. **Deployment Ambiguity:** When deploying updates via GitHub Container Registry (GHCR) and automated continuous deployment (Watchtower), store managers, QA, and developers cannot currently verify from within the web interface whether a container update has pulled and restarted the latest image.
2. **Stale Cache & Service Worker Diagnostics:** When testing changes on mobile or desktop (especially with PWA Service Workers), users need an immediate visual indicator in the footer to verify if they are viewing the new release or cached assets.
3. **Incident Triaging & Bug Reporting:** Bug reports and screenshots sent by staff will automatically capture the exact build timestamp and Git commit SHA in the footer, removing guesswork about whether an issue occurred on an older build.
4. **Environment Differentiation:** Visual badge indicating whether the app is running in `Production (Docker)`, `Staging`, or `Local Development`.

---

## 2. Tech Stack & Architecture Context

- **Runtime / Framework:** Python 3.13, Django 5.1+
- **Containerization:** Docker multi-stage / slim (`python:3.13-slim-bookworm`), Docker Compose (`docker-compose.yml`, `docker-compose.prod.yml`)
- **CI/CD Pipeline:** GitHub Actions (`.github/workflows/ci.yml`), GitHub Container Registry (`ghcr.io/saert3311/2nd-hand-manager:latest`)
- **Frontend / Styling:** Django Templates (`inventory/templates/inventory/base.html`), Tailwind CSS
- **Internationalization (i18n):** Bilingual support (Spanish `es` default, English `en`) via Django `gettext`
- **Context Injection:** Dedicated Django Context Processor (`build_info` in `inventory/context_processors.py`)

---

## 3. Executable Commands

- **Local Dev Server:** `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
- **Run Unit & Integration Tests:** `.venv\Scripts\python.exe manage.py test tests.test_build_info`
- **Run Full Test Suite:** `.venv\Scripts\python.exe manage.py test`
- **Code Linter:** `.venv\Scripts\ruff.exe check .`
- **Compile Translations:** `.venv\Scripts\python.exe manage.py compile_locales`
- **Local Docker Build Test:** `docker build -t secondhand-staging:test .`
- **Docker Build with Build Args:** `docker build --build-arg BUILD_TIME="$(Get-Date -UFormat '%Y-%m-%d %H:%M:%S UTC')" --build-arg BUILD_COMMIT="local-test" -t secondhand-staging:test .`

---

## 4. Project Structure & Affected Modules

```
inventory/
├── context_processors.py             # Add build_info context processor injecting build metadata
├── services/
│   └── version_service.py            # Resolver detecting env vars, build file, git commit fallback
├── templates/inventory/
│   └── base.html                     # Update <footer> to display compilation timestamp, SHA & badge
Dockerfile                            # Add ARG BUILD_TIME, ARG BUILD_COMMIT, ARG APP_VERSION & default file generation
docker-compose.yml                    # (Optional) pass build args during compose build
docker-compose.prod.yml               # Maintain environment compatibility
.github/workflows/
└── ci.yml                            # Inject BUILD_TIME and BUILD_COMMIT in build-push-action steps
locale/
├── es/LC_MESSAGES/django.po          # Spanish translations for "Build", "Version", "Local Development"
└── en/LC_MESSAGES/django.po          # English translations
tests/
└── test_build_info.py                # Unit tests verifying context processor, fallback logic, and footer rendering
```

---

## 5. Architectural Design & Resolution Strategy

### 5.1 Hierarchical Build Info Resolution (`version_service.py`)

The application must deterministically resolve build metadata without runtime latency or crashes. The `get_build_info()` service inspects three cascading sources, caching the result in memory on startup:

1. **Environment Variables (Primary in Docker / Cloud):**
   - `APP_BUILD_TIME` (e.g. `2026-10-19 18:30:00 UTC` or ISO-8601 string)
   - `APP_BUILD_COMMIT` (e.g. `9d931b9` or full Git SHA)
   - `APP_VERSION` (e.g. `v1.1.0` or package version)
   - `APP_ENV` (e.g. `production`, `staging`, `development`)

2. **Baked-in Build File (`/app/build_info.json` or `/app/build_date.txt`):**
   - Generated during `docker build` inside `Dockerfile` if arguments or environment variables were omitted.
   - Guarantees that any plain `docker build .` or `docker compose build` automatically captures the exact build execution timestamp.

3. **Dynamic Git Fallback (Development Environment):**
   - When running locally outside Docker (e.g. `python manage.py runserver`) where no build file or environment variables exist:
   - Queries `git log -1 --format="%cd" --date=format:"%Y-%m-%d %H:%M UTC"` and `git rev-parse --short HEAD`.
   - If Git is not installed or repository metadata is absent, cleanly falls back to:
     - `build_time`: Application startup timestamp or `None`
     - `commit_short`: `None`
     - `environment`: `"development"`
     - `label`: `"Desarrollo local" / "Local Development"`

### 5.2 Context Processor Contract (`inventory/context_processors.py`)

Exposes a dictionary under the `build_info` key to all templates:

```python
def build_info(request):
    return {
        "build_info": {
            "build_time": "2026-10-19 18:30:00 UTC",
            "commit_short": "9d931b9",
            "version": "v1.1.0",
            "is_docker": True,
            "environment": "production",
            "env_badge_class": "bg-emerald-100 text-emerald-800 border border-emerald-300",
            "formatted_display": "2026-10-19 18:30 UTC (9d931b9)",
        }
    }
```

### 5.3 Dockerfile Metadata Embedding

Update `Dockerfile` with build arguments:

```dockerfile
# Build metadata arguments
ARG BUILD_TIME=""
ARG BUILD_COMMIT=""
ARG APP_VERSION="1.0.0"

ENV APP_BUILD_TIME=${BUILD_TIME} \
    APP_BUILD_COMMIT=${BUILD_COMMIT} \
    APP_VERSION=${APP_VERSION}

# If BUILD_TIME is empty during local build, generate build_date.txt at image build time
RUN if [ -z "$BUILD_TIME" ]; then \
        date -u +"%Y-%m-%d %H:%M:%S UTC" > /app/build_date.txt; \
    else \
        echo "$BUILD_TIME" > /app/build_date.txt; \
    fi && \
    if [ -n "$BUILD_COMMIT" ]; then \
        echo "$BUILD_COMMIT" > /app/build_commit.txt; \
    fi
```

### 5.4 GitHub Actions CI Workflow Update (`.github/workflows/ci.yml`)

Pass `build-args` to `docker/build-push-action@v6` in `publish-image` and `docker-build-and-smoke-test`:

```yaml
build-args: |
  BUILD_TIME=${{ steps.build_time.outputs.now }}
  BUILD_COMMIT=${{ github.sha }}
  APP_VERSION=${{ github.ref_name }}
```

---

## 6. UI & Footer Presentation Specification

In [`inventory/templates/inventory/base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html), update the footer to render cleanly across desktop and mobile screens ($390 \times 844$):

```html
<footer class="bg-white border-t border-slate-200 py-4 px-4 text-center text-xs text-slate-400 space-y-1.5" role="contentinfo">
  <div>
    {% trans "2ndHand Product Intake & Staging Hub • Powered by Django & Gemini Vision" %}
  </div>
  <div class="flex items-center justify-center flex-wrap gap-x-2 gap-y-1 text-slate-500 text-[11px] sm:text-xs">
    <span class="inline-flex items-center gap-1 font-mono">
      <span aria-hidden="true">⏱️</span>
      <span class="text-slate-400">{% trans "Build:" %}</span>
      <span class="font-medium text-slate-600" id="footer-build-time">{{ build_info.build_time }}</span>
    </span>
    {% if build_info.commit_short %}
    <span class="text-slate-300">•</span>
    <span class="inline-flex items-center gap-1 font-mono">
      <span aria-hidden="true">🔖</span>
      <span class="text-slate-400">{% trans "Commit:" %}</span>
      <span class="font-medium text-slate-600" id="footer-build-sha">{{ build_info.commit_short }}</span>
    </span>
    {% endif %}
    {% if build_info.environment_badge %}
    <span class="text-slate-300">•</span>
    <span class="px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider {{ build_info.badge_css }}">
      {{ build_info.environment_badge }}
    </span>
    {% endif %}
  </div>
</footer>
```

### Mobile Responsive Constraints
- Wrapping: Flex container with `flex-wrap justify-center gap-x-2 gap-y-1` ensures elements never overflow the horizontal bounds on mobile screens.
- Typography: Uses `text-[11px] sm:text-xs` conforming to the mobile readability design rules established in Phase 22.

---

## 7. Testing Strategy

1. **Unit Tests (`tests/test_build_info.py`)**:
   - `test_build_info_from_environment_variables`: Assert context processor correctly parses `APP_BUILD_TIME`, `APP_BUILD_COMMIT`, and `APP_VERSION`.
   - `test_build_info_from_file_fallback`: Assert fallback to `/app/build_date.txt` when environment variables are unset.
   - `test_build_info_from_git_fallback`: Assert fallback to git commit timestamp/hash in local repository.
   - `test_build_info_graceful_missing_fallback`: Assert non-crashing fallback when no metadata source is available.
   - `test_footer_renders_build_info_in_templates`: Test GET request to `/dashboard/` and `/login/` verifying presence of `#footer-build-time` and formatted content.
   - `test_build_info_spanish_localization`: Assert translated tokens ("Compilación", "Desarrollo local") render when Spanish locale is active.
2. **Smoke Test in Docker Container**:
   - Verify that container launched during CI (`docker-build-and-smoke-test` in `.github/workflows/ci.yml`) exposes `#footer-build-time` with valid timestamp in HTTP response.

---

## 8. Boundaries

- **Always Do:**
  - Cache resolved build metadata in memory so filesystem / git checks occur at most once upon server startup.
  - Provide safe, non-crashing fallbacks for all environments (CI, local Docker, Windows PowerShell, Linux container).
  - Support bilingual localization (`es`/`en`).
  - Maintain clean HTML semantics with standard IDs (`#footer-build-time`, `#footer-build-sha`) for test verification.
- **Ask First:**
  - Modifying external CI secrets or deploying to remote servers.
  - Adding external dependencies (standard library and existing settings are sufficient).
- **Never Do:**
  - Execute blocking shell calls or slow subprocesses on every HTTP request.
  - Expose sensitive environment keys, internal server file paths, or private credentials in the footer.
  - Break existing footer layout or mobile responsive wrapping.

---

## 9. Success Criteria

- [ ] Build date and time is prominently and legibly displayed in the application footer across all pages (`base.html`).
- [ ] Docker builds automatically bake in the exact build timestamp and Git commit SHA.
- [ ] Local development cleanly falls back to current Git commit info or "Local Development" without crashing.
- [ ] Footer renders responsively on mobile ($390 \times 844$) without overflow or awkward line breaks.
- [ ] Bilingual localization supports Spanish ("Compilación:") and English ("Build:").
- [ ] Full test suite passes with 100% test coverage and 0 regressions (`python manage.py test`).
- [ ] Code passes `ruff check .` with zero errors.

---

## 10. Open Questions for User Alignment

1. **Display Format & Precision:**
   - **Option A (Recommended — UTC Date & Time + Commit SHA):** e.g., `Build: 2026-10-19 18:30 UTC • Commit: 9d931b9 • Docker Prod`. Explicit UTC timestamp prevents timezone confusion between servers and clients.
   - **Option B (Date only):** e.g., `Build: 2026-10-19 • Commit: 9d931b9`.
   - **Option C (Local Spanish Format):** e.g., `Compilación: 19/10/2026 20:30 (Madrid)`.

2. **Commit SHA Inclusion:**
   - **Option A (Recommended — Date + Short SHA):** Display both the build timestamp and short Git commit hash (`7-character SHA`).
   - **Option B (Timestamp only):** Display strictly the date and time without the commit hash.

3. **Environment Pill / Badge:**
   - **Option A (Recommended — With Environment Pill):** Include a subtle status badge (e.g. `PROD` in emerald, `STAGING` in amber, or `DEV` in slate).
   - **Option B (Minimalist — Text Only):** Pure text without any environment badge.

4. **Footer Visibility:**
   - **Option A (Recommended — All Pages & All Users):** Visible in the footer across all views (authenticated and unauthenticated login screen) so anyone inspecting the app can verify the build version.
   - **Option B (Authenticated Users Only):** Hide on the public login screen, display only after login.
