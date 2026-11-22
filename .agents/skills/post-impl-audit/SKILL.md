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

Run this workflow after completing implementation and tests (Step 5) and **before** asking the user to merge into `master` (Step 6). It enforces unbiased subagent verification without bloating `AGENTS.md` or producing duplicate reports.

---

## 1. Tier Routing Matrix (`git diff --name-only master...HEAD`)

Inspect the branch diff first:

```powershell
git diff --name-only master...HEAD
```

Route using the **highest applicable tier** (`Tier 3` is additive to `Tier 1`/`Tier 2`):

| Tier | Trigger (`git diff --name-only master...HEAD`) | Required Audits |
| :--- | :--- | :--- |
| **Tier 0** | Docs, comments, `.md` files, or `.po`/`.mo` translations only | Standard CLI quality gates only (`ruff`, `check`, `compile_locales`, `test`) |
| **Tier 1** | Any `.py`, `Dockerfile`, `.github/`, `pyproject.toml`, `requirements*.txt`, or config file | CLI gates + **Fresh `code-reviewer` subagent** (fused `code-review-and-quality` + `ponytail-review`) |
| **Tier 2** | Any `*.html`, `*.css`, `*.js`, `storefront/templates/`, `storefront/static/`, `inventory/templates/`, or `inventory/static/` | Pre-edit DemoLab read + **Tier 1** + **Live `browser` subagent** across all 4 viewports *(can run in parallel with Tier 1)* |
| **Tier 3** | Release version bump (`APP_VERSION` in `config/settings.py`), multi-phase milestone, or explicit user request | **Tier 1 / Tier 2** + **Whole-repo `/ponytail-audit`** via fresh subagent |

---

## 2. Tier 1: Independent Code & Lean Audit (Fresh `code-reviewer` Subagent)

**Self-review is forbidden.** The agent that implemented the code must never sign off its own diff. Launch a fresh `code-reviewer` subagent (`invoke_subagent`) with the prompt template below so it reads the diff cold.

### `code-reviewer` Delegation Prompt Template

```text
Perform an independent, unified pre-merge audit of branch `<branch-name>` against `master`.

1. Inspect `git diff --name-only master...HEAD` and `git diff master...HEAD`, plus any matching PRD/idea doc (`docs/prds/`, `docs/ideas/`) and connected callers/tests.
2. Read and apply BOTH installed skills without emitting two redundant reports:
   - `code-review-and-quality` (`C:\Users\Jose\.gemini\config\plugins\agent-skills\skills\code-review-and-quality\SKILL.md`): 5 axes (Correctness, Readability, Architecture, Security, Performance), spec fidelity, file-size/structural remedies, mutation spot-check on one key added branch when practical, and severity labels (`Critical`, `Required`, `Optional`, `Nit`).
   - `ponytail-review` (`C:\Users\Jose\.gemini\config\plugins\ponytail\skills\ponytail-review\SKILL.md`): concrete failure cases only, real-load/scale risks (assumed load: small second-hand shop staging hub + public storefront on single-node SQLite + Gunicorn Docker), missing tests on risky logic, plain-English 4-part format (`What this is`, `Problem`, `Fix`, `If we skip it`), and `Lean: -N lines possible` cuts (dead code, duplicate helpers, YAGNI).
3. Emit ONE deduplicated report (no vague worries or style taste) ending with:
   - `Verdict: Ship.` OR `Verdict: Fix [numbers] first.`
   - `Lean: -<N> lines possible.` (when lean cuts exist)
   - `Not checked: <anything skipped or unrun>`
```

### Blocking Rule
- Fix **every** `Critical`, `Required`, and `Must fix` item before proceeding.
- Commit fixes as `fix(<scope>): address post-implementation audit findings` and re-run all CLI quality gates (`ruff check .`, `manage.py check`, `manage.py compile_locales`, `manage.py test`).

---

## 3. Tier 2: UI Craft & Live Browser Verification (DemoLab + `browser` Subagent)

### Surface Precedence (Read `gemini-frontend-design` Before Editing UI)
Read `C:\Users\Jose\.gemini\config\plugins\demolab\skills\gemini-frontend-design\SKILL.md` *before* writing or modifying templates/styles, and apply its Section 5 visual critique under these surface rules:

| Surface | Governing Tokens & Baseline (Takes Precedence) | What Gemini DemoLab Governs |
| :--- | :--- | :--- |
| **`storefront/`** *(Public Site)* | `docs/stitch_references/DESIGN_SYSTEM.md` (`Rápido Pack` palette, `Outfit` / `Hanken Grotesk`) overrides greenfield palette defaults | Opening viewport fit, layout rhythm, hierarchy, copy/transition hygiene, zero decorative clutter, visual critique |
| **`inventory/templates/`** *(Staff Staging Hub)* | Tailwind utilities, semantic workflow status badges/pills, and OPPO A74 low-DPI ergonomics override marketing/anti-badge rules | Information hierarchy, spacing, transition hygiene (no `transition-all`), responsive alignment, visual critique |

### Local Dev Server Launch (Windows PowerShell)
Start Django in the background (`run_command` with `IsDaemon=true`, `WaitMsBeforeAsync=3000`):

```powershell
$env:TURNSTILE_ENABLED='False'; $env:DEBUG='True'; .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

- `TURNSTILE_ENABLED=False` prevents Cloudflare Turnstile from blocking `/login/` locally (per `config/settings.py`).
- `--noreload` prevents Django's auto-reloader from leaving orphaned child Python processes when you stop the daemon.

### Disposable Local Dev Accounts (Authenticated Routes Only)
If inspecting staff views (`/dashboard/`, `/intake/`, `/pallets/`, `/products/<pk>/`), create ephemeral `_audit_tmp_` accounts in local `db.sqlite3` with a runtime-generated random password. **Never** commit credentials or alter real user accounts.

Create `_audit_tmp_manager` (matching `ROLE_MANAGER = "managers"` in `inventory/permissions.py`):

```powershell
.venv\Scripts\python.exe manage.py shell -c "import secrets; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; U = get_user_model(); pw = secrets.token_urlsafe(16); u, _ = U.objects.get_or_create(username='_audit_tmp_manager', defaults={'is_staff': True}); u.is_staff = True; u.set_password(pw); u.save(); g, _ = Group.objects.get_or_create(name='managers'); u.groups.add(g); print('USER=_audit_tmp_manager PASS=' + pw)"
```

If assistant-specific permissions or `/intake/` flows changed, also create `_audit_tmp_assistant` (`ROLE_ASSISTANT = "assistants"`):

```powershell
.venv\Scripts\python.exe manage.py shell -c "import secrets; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; U = get_user_model(); pw = secrets.token_urlsafe(16); u, _ = U.objects.get_or_create(username='_audit_tmp_assistant', defaults={'is_staff': False}); u.is_staff = False; u.set_password(pw); u.save(); g, _ = Group.objects.get_or_create(name='assistants'); u.groups.add(g); print('USER=_audit_tmp_assistant PASS=' + pw)"
```

### Live `browser` Subagent Brief (`invoke_subagent(TypeName="browser", ...)`)
Verify every changed or affected public (`/`, `/tienda/`, `/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`) and/or staff (`/login/`, `/dashboard/`, `/intake/`, `/pallets/`, `/products/<pk>/`) route across **all 4 mandatory viewports**:

1. **`1440×900`** — Desktop opening viewport **AND** scrolled below-the-fold sections.
2. **`390×844`** — Standard mobile (DemoLab Section 5 baseline).
3. **`360×800`** — OPPO A74 standard narrow Android.
4. **`320×711`** — OPPO A74 zoomed / low-DPI Android.

Require the `browser` subagent to check and report:
- **Zero horizontal overflow:** `document.documentElement.scrollWidth <= document.documentElement.clientWidth` at every viewport.
- **Clean runtime:** Zero console errors, uncaught page errors, broken `<img>` loads, or unexpected `4xx`/`5xx` network responses.
- **DemoLab Section 5 & `AGENTS.md` UI checks (calibrated by surface):** Single-line desktop navigation, clean scrolled header separation, zero text/visual collisions or clipped controls, consistent typography scale, no decorative clutter, no stacked dashboard status tabs (*apilación*), `>= 16px` mobile inputs, and readable WCAG AA contrast.
- **Interactive flows:** Exercise any forms, filters, tabs, modals, or buttons touched by the branch.

### Mandatory Cleanup & Screenshot Hygiene
After the `browser` subagent finishes (and after verifying any UI fixes):
1. Stop the background `runserver` task via `manage_task(Action="kill", TaskId=...)`.
2. Delete all disposable local dev users from `db.sqlite3`:
   ```powershell
   .venv\Scripts\python.exe manage.py shell -c "from django.contrib.auth import get_user_model; count, _ = get_user_model().objects.filter(username__startswith='_audit_tmp_').delete(); print('Deleted audit users:', count)"
   ```
3. **Screenshot hygiene:** Keep inspection screenshots strictly in the conversation artifact directory (`<appDataDir>\brain\<conversation-id>\`). Never save temporary PNGs or `browser_verification_screenshots/` directories inside the git workspace.

---

## 4. Tier 3: Release / Milestone Whole-Repo Audit (`/ponytail-audit`)

Triggered when preparing a version bump (`APP_VERSION` in `config/settings.py`), completing a major multi-phase milestone, or when explicitly requested by the user:
1. Dispatch a fresh `code-reviewer` (or `research`) subagent to read `C:\Users\Jose\.gemini\config\plugins\ponytail\skills\ponytail-audit\SKILL.md` and audit the repository assuming single-node SQLite + Gunicorn Docker load for a small second-hand shop staging hub + public storefront.
2. Fix all `Must fix` findings before tagging or requesting merge; note any deferred `Should fix` / `Nice to have` findings in the Merge Readiness Packet.

---

## 5. Step 6 Merge Readiness Packet Template

Include this packet whenever requesting user approval to merge into `master`:

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
- Disposable `_audit_tmp_*` users deleted, local `runserver` stopped, and no temporary screenshots/files left in workspace.
```
