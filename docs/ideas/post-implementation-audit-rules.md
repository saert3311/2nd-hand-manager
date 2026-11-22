# Post-Implementation Code & UI Audit Gate

## Problem Statement
How might we guarantee that every new implementation in `epic-tesla` undergoes an unbiased code-quality review and—when UI changes—a real DemoLab + live-browser visual critique before merge, without bloating `AGENTS.md`, duplicating overlapping audit reports, or bogging down trivial fixes?

## Recommended Direction
Adopt a **Two-File Core with Tier 0–3 Routing**: keep root `AGENTS.md` compact by adding a lean **Rule #7**, a new **Step 5.5 (Post-Implementation Audit)**, a compact **UI Surface Precedence** note, and a required **Merge Readiness Packet** inside **Step 6**. Put the complete audit runbook in a single version-controlled workspace skill at `.agents/skills/post-impl-audit/SKILL.md` so Antigravity loads it on demand (progressive disclosure) instead of burning context on every turn.

To prevent self-review blindness and duplicate reports, Step 5.5 forbids the implementing agent from grading its own work and routes changes through explicit tiers based on `git diff --name-only master...HEAD`. Code changes trigger one fresh `code-reviewer` subagent (supplied with a parent-prepared diff bundle) that fuses `/code-review-and-quality` (5 axes, spec fidelity, severity labels) with `/ponytail-review` (concrete failure cases, real-load risk, plain-English `Lean: -N lines` cuts) into a single deduplicated scorecard. UI changes require reading Gemini DemoLab (`gemini-frontend-design`) *before* editing—with explicit precedence for `storefront/templates/storefront/base_public.html` brand tokens on `storefront/` and OPPO A74 rules + semantic badges on `inventory/`—and end with a live `browser` subagent critique across Desktop (above & below the fold), `390×844`, `360×800`, and `320×711`. Full-repo `/ponytail-audit` is reserved for releases, milestones, or explicit requests.

## Decisions Confirmed
1. **Fresh Branch Target:** Implement the rules and workspace skill on a dedicated feature branch `feat/post-impl-audit-rules` branched off `master` per `AGENTS.md` Rule #2.
2. **Disposable Dev User Accounts for Authenticated Browser Checks:** For Tier 2 live UI checks on authenticated staff routes (`/dashboard/`, `/intake/`, `/pallets/`, `/products/<pk>/`), agents create and immediately delete ephemeral `_audit_tmp_*` local dev users via `manage.py shell` with runtime-generated passwords rather than storing credentials or modifying real user accounts.

## Key Assumptions to Validate
- [ ] **Fused review preserves both lenses:** A single fresh `code-reviewer` subagent reading both `code-review-and-quality` and `ponytail-review` catches both spec/security issues *and* concrete bloat/load cuts without watering either down — *Test by running `/post-impl-audit` on the next feature branch and verifying the output includes both severity-labeled 5-axis findings and a concrete `Lean: -N lines` / failure-case pass.*
- [ ] **Live browser verification works reliably on authenticated staff views:** Agents can start a local Django server (with `TURNSTILE_ENABLED=False` in local dev, per `config/settings.py`), create disposable `_audit_tmp_*` accounts, log into `/dashboard/`, `/intake/`, or `/products/<pk>/`, inspect all 4 viewports, clean up the temp users, and shut the server down cleanly without leaving untracked screenshots in git — *Test on one `storefront/` change and one `inventory/` UI change.*
- [ ] **Visible Merge Readiness Packet drives compliance without hooks:** Requiring the structured audit summary at Step 6 prevents agents from skipping audits in long sessions — *Test across the next 3–5 branches; if agents still forget Step 5.5, add a lightweight `.agents/hooks.json` reminder later.*

## MVP Scope
**In scope:**
1. **`AGENTS.md`:** Add Rule #7, Step 5.5, UI Surface Precedence (DemoLab calibration), and the Step 6 Merge Readiness Packet gate while remaining comfortably under the 24,000-byte per-file rule cap.
2. **`.agents/skills/post-impl-audit/SKILL.md`:** Tier 0–3 routing matrix, fresh `code-reviewer` delegation brief, DemoLab + live `browser` subagent checklist (with local server and disposable dev user snippets), Tier 3 `/ponytail-audit` trigger, and Step 6 Merge Readiness Packet template.

**Out of scope:**
- No code changes to Django application logic, CI workflows, or Playwright test suites.

## Not Doing (and Why)
- **Whole-repo `/ponytail-audit` on every commit/PR** — `/ponytail-audit` scans the entire repository; running it on every small fix burns tokens and repeatedly reports pre-existing repo items. Diff-scoped `/ponytail-review` handles day-to-day branches, while `/ponytail-audit` stays sharp for Tier 3 releases and milestones.
- **Separate `storefront/AGENTS.md` and `inventory/templates/AGENTS.md` files** — Premature rule sprawl; directory rules only load once files inside those folders are opened, which can miss early planning. Keep a compact surface table in root `AGENTS.md` + the skill, and split only if surface-specific rules outgrow it.
- **Mechanical `.agents/hooks.json` hard-blocks** — Hooks run synchronously on every matching event and can frustrate legitimate exploration or intermediate commits. Prove the workflow via the Step 6 Merge Readiness Packet first.
- **Custom Python `run_workflow` orchestration script** — Over-engineered for 2 parallel subagents (`code-reviewer` + `browser`) that the main agent can dispatch natively via the skill.
- **Running `/code-review-and-quality` and `/ponytail-review` as two separate sequential reports** — They overlap ~60%; fusing them into one deduplicated fresh-subagent scorecard keeps feedback high-signal and readable.
