---
name: post-impl-audit
description: >-
  Mandatory post-implementation audit and live UI visual verification gate for
  epic-tesla. Routes branches through Tiers 0-3 (fresh code-reviewer fusing
  code-review-and-quality + ponytail-review, Gemini DemoLab + live browser
  viewport critique on UI changes, and whole-repo ponytail-audit on releases)
  and produces the Step 6 Merge Readiness Packet. Use after finishing any
  feature, bugfix, UI change, or release prep before asking to merge into master.
---

# Post-Implementation Code & UI Audit

Run this workflow after Step 5 (including any release bump) and **before** requesting merge approval in Step 6. It enforces unbiased verification without duplicating rules across files.

---

## 1. Tier Routing Matrix

Inspect `git diff --name-only master...HEAD` and apply the **highest matching tier** (`Tier 3` is additive to `Tier 1`/`Tier 2`):

| Tier | Trigger (`git diff --name-only master...HEAD`) | Required Audits |
| :--- | :--- | :--- |
| **Tier 0** | **Only** files under `docs/`, `tasks/`, `locale/` (`.po`/`.mo`), or root `README.md`, `CHANGELOG.md`, `SPEC.md` | Standard CLI quality gates only (`ruff`, `check`, `compile_locales`, `test`) |
| **Tier 1** | Any `.py`, `AGENTS.md`, `.agents/`, `Dockerfile`, `.dockerignore`, `docker/`, `.github/`, `.env.example`, `pyproject.toml`, `requirements*.txt`, `*.sh`, `*.yml`, `*.yaml`, `*.toml`, or `*.json` file | CLI gates + **Parent-prepared diff bundle** + **Fresh `code-reviewer` subagent** (fused `code-review-and-quality` + `ponytail-review`) |
| **Tier 2** | Any `*.html`, `*.css`, `*.js`, `storefront/templates/`, `storefront/static/`, `inventory/templates/`, or `inventory/static/` file | Pre-edit DemoLab read + **Tier 1** + **Live `browser` subagent** across 4 viewports *(can run in parallel with Tier 1)* |
| **Tier 3** | Release bump (`APP_VERSION` in `config/settings.py`, committed at end of Step 5), major multi-phase milestone, or explicit user request | **Tier 1 / Tier 2** + **Whole-repo `ponytail-audit`** via fresh subagent |

---

## 2. Tier 1: Independent Code & Lean Audit (`code-reviewer` Subagent)

**Self-review is forbidden.** Because `code-reviewer` is **read-only** (`read_file` only — no shell, grep, or directory listing tools), prepare its context first:

### Parent Preparation Step (Required Before Calling `invoke_subagent`)
1. Write `git status --short`, `git diff --name-only master...HEAD`, and `git diff master...HEAD` to `<appDataDir>\brain\<conversation-id>\scratch\branch_audit.diff`.
2. When functions, signatures, or models change, grep connected callers and write matches to `<appDataDir>\brain\<conversation-id>\scratch\branch_audit_context.txt`.
3. Pass those exact scratch paths plus changed files and matching PRD/idea doc paths in the subagent prompt.

### `code-reviewer` Delegation Prompt Template

```text
Perform an independent, unified pre-merge audit of branch `<branch-name>` against `master`.

1. Read the parent-prepared diff bundle (`<path-to>/scratch/branch_audit.diff`), caller context (`<path-to>/scratch/branch_audit_context.txt` if present), changed files, matching PRD/idea doc, and tests using `read_file` only (do not attempt shell commands or file edits).
2. Read and apply BOTH installed skills (`code-review-and-quality` and `ponytail-review`) in ONE unified, deduplicated report:
   - From `code-review-and-quality`: 5 axes (Correctness, Readability, Architecture, Security, Performance), spec fidelity, file-size/structural remedies, and severity labels (`Critical`, `Required`, `Optional`, `Nit`). For risky conditional logic (auth, pricing, lifecycle state), name the highest-value untested branch/mutation case so the parent can add or verify a regression test.
   - From `ponytail-review`: concrete failure cases only, real-load/scale risks (single-shop Django + SQLite + Gunicorn Docker), missing tests on risky logic, plain-English 4-part format (`What this is`, `Problem`, `Fix`, `If we skip it`), and `Lean: -N lines possible` cuts (dead code, duplicate helpers, YAGNI).
3. Emit ONE report (no vague worries or style taste) ending with:
   - `Verdict: Ship.` OR `Verdict: Fix [numbers] first.`
   - `Lean: -<N> lines possible.` (when lean cuts exist)
   - `Not checked: <anything not in the prepared bundle>`
```

### Blocking Rule
- Fix **every** `Critical`, `Required`, and `Must fix` item (and add any parent-verified regression test flagged by the reviewer) before proceeding.
- Commit fixes as `fix(<scope>): address post-implementation audit findings` and re-run all CLI quality gates (`ruff check .`, `manage.py check`, `manage.py compile_locales`, `manage.py test`).

---

## 3. Tier 2: UI Craft & Live Browser Verification (DemoLab + `browser` Subagent)

### Pre-Edit Design Check & Surface Precedence
Before editing UI files, read the `gemini-frontend-design` skill and follow the canonical **UI Surface Precedence** rules in `AGENTS.md` Section 4 (`storefront/templates/storefront/base_public.html` brand tokens for `storefront/`; Tailwind + semantic status badges + OPPO A74 low-DPI ergonomics for `inventory/templates/`).

### Local Dev Server Launch (Windows PowerShell)
Start Django as a background daemon (`run_command` with `IsDaemon=true`, `WaitMsBeforeAsync=3000`):

```powershell
$env:TURNSTILE_ENABLED='False'; $env:DEBUG='True'; .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

- `TURNSTILE_ENABLED=False` keeps local `/login/` testable without Cloudflare Turnstile tokens; `--noreload` avoids orphaned child reloader processes on daemon kill.

### Disposable Local Dev Accounts (Authenticated Routes Only)
Before creating ephemeral `_audit_tmp_` users, verify `DATABASE_URL` is unset (so writes hit local `db.sqlite3` only, never a remote DB) and local migrations are current (`manage.py migrate --check`, running `manage.py migrate` if needed):

```powershell
if ($env:DATABASE_URL) { throw "Refusing to create _audit_tmp_* users while DATABASE_URL is set" }
.venv\Scripts\python.exe manage.py migrate --check
```

Create `_audit_tmp_manager` (`ROLE_MANAGER = "managers"` in `inventory/permissions.py`):

```powershell
.venv\Scripts\python.exe manage.py shell -c "import secrets; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; U = get_user_model(); pw = secrets.token_urlsafe(16); u, _ = U.objects.get_or_create(username='_audit_tmp_manager', defaults={'is_staff': True}); u.is_staff = True; u.set_password(pw); u.save(); g, _ = Group.objects.get_or_create(name='managers'); u.groups.add(g); print('USER=_audit_tmp_manager PASS=' + pw)"
```

When assistant flows or `/intake/` permissions changed, also create `_audit_tmp_assistant` (`ROLE_ASSISTANT = "assistants"`):

```powershell
.venv\Scripts\python.exe manage.py shell -c "import secrets; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; U = get_user_model(); pw = secrets.token_urlsafe(16); u, _ = U.objects.get_or_create(username='_audit_tmp_assistant', defaults={'is_staff': False}); u.is_staff = False; u.set_password(pw); u.save(); g, _ = Group.objects.get_or_create(name='assistants'); u.groups.add(g); print('USER=_audit_tmp_assistant PASS=' + pw)"
```

### Live `browser` Subagent Brief (`invoke_subagent(TypeName="browser", ...)`)
Verify every changed or affected public (`/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) and/or staff (`/login/`, `/dashboard/`, `/intake/`, `/pallets/`, `/products/<pk>/`) route across **all 4 mandatory viewports**:

1. **`1440×900`** — Desktop opening viewport **AND** scrolled below-the-fold sections.
2. **`390×844`** — Standard mobile (DemoLab Section 5 baseline).
3. **`360×800`** — OPPO A74 standard narrow Android.
4. **`320×711`** — OPPO A74 zoomed / low-DPI Android.

Verify and report:
- **Zero horizontal overflow:** `document.documentElement.scrollWidth <= document.documentElement.clientWidth` at every viewport.
- **Clean runtime:** Zero console errors, uncaught exceptions, broken `<img>` loads, or unexpected `4xx`/`5xx` network responses.
- **DemoLab Section 5 & `AGENTS.md` UI checks (surface-calibrated):** Single-line desktop navigation, clean scrolled header separation, zero text/visual collisions or clipped controls, consistent typography scale, no decorative clutter, no stacked dashboard tabs (*apilación*), `>= 16px` mobile inputs, and readable WCAG AA contrast.
- **Interactive flows:** Exercise any forms, filters, tabs, modals, or buttons touched by the branch.

### Mandatory Cleanup & Screenshot Hygiene
1. Stop the background `runserver` task via `manage_task(Action="kill", TaskId=...)`.
2. Delete all `_audit_tmp_*` users **and any dummy `Product`/`Pallet`/`Provider` test rows** created during interactive browser verification:
   ```powershell
   .venv\Scripts\python.exe manage.py shell -c "from django.contrib.auth import get_user_model; count, _ = get_user_model().objects.filter(username__startswith='_audit_tmp_').delete(); print('Deleted audit users:', count)"
   ```
3. **Screenshot hygiene:** Keep screenshots strictly inside `<appDataDir>\brain\<conversation-id>\` — never leave PNGs or `browser_verification_screenshots/` inside the git workspace.

---

## 4. Tier 3: Release / Milestone Whole-Repo Audit (`ponytail-audit`)

Triggered on release bumps (`APP_VERSION` in `config/settings.py`), multi-phase milestones, or explicit user request:
1. Parent writes `git ls-files` and `git status --short` to `<appDataDir>\brain\<conversation-id>\scratch\repo_manifest.txt`.
2. Delegate a fresh `code-reviewer` subagent (passing `repo_manifest.txt` and entry points `README.md`, `Dockerfile`, `.github/workflows/ci.yml`, `config/settings.py`, `config/urls.py`, `inventory/`, `storefront/`) or a `research` subagent to read and execute the `ponytail-audit` skill for single-shop SQLite + Gunicorn Docker load.
3. Resolve all `Must fix` findings before tagging or requesting merge; note deferred `Should fix` / `Nice to have` items in the Merge Readiness Packet.

---

## 5. Step 6 Merge Readiness Packet Template

```markdown
## Merge Readiness Packet — `<branch-name>`

- **Diff Scope (`master...HEAD`):** <summary of files / commits>
- **Audit Tier(s) Applied:** <Tier 0 | Tier 1 | Tier 2 | Tier 3>

### Automated Quality Gates
| Gate | Command | Result |
| :--- | :--- | :--- |
| Ruff Lint | `.venv\Scripts\ruff.exe check .` | PASS / FAIL |
| Django Check | `.venv\Scripts\python.exe manage.py check` | PASS / FAIL |
| Locales Sync | `.venv\Scripts\python.exe manage.py compile_locales` | PASS / FAIL |
| Test Suite | `.venv\Scripts\python.exe manage.py test` | PASS (N tests) / FAIL |

### Independent Code & Lean Audit (Tier 1)
- **Reviewer Verdict:** `<Verdict from fresh code-reviewer subagent>`
- **Critical / Required / Must Fix Items Resolved:** <list or "None found">
- **Lean Summary:** `<Lean: -N lines possible / applied / none>`

### Live UI & Browser Critique (Tier 2)
- **Routes & Flows Checked:** <list or "N/A — no UI files changed">
- **Viewport Matrix:** `1440×900` (above & below fold) | `390×844` | `360×800` | `320×711`
- **Visual & Runtime Findings:** <overflow/console/DemoLab findings & fixes>

### Whole-Repo Audit (Tier 3)
- **Ponytail Audit Verdict:** `<Verdict & Must-fix resolution, or "N/A — not a release/milestone">`

### Cleanup Confirmation
- Disposable `_audit_tmp_*` users and any interactive test records deleted, local `runserver` stopped, and no temporary screenshots/files left in workspace.
```
