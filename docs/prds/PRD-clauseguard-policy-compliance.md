# PRD: ClauseGuard — Cost-Optimized Multi-Platform Policy Compliance (Phase 48)

## 1. Objective

### Problem Statement
In **2ndHand Staging Hub**, warehouse assistants and store managers catalog varied liquidation pallet and walk-in items destined for **Wallapop, Vinted, eBay, Milanuncios, and the Rápido Pack Public Storefront**. Each platform enforces strict Terms & Conditions regarding prohibited or restricted items (e.g., Vinted prohibits opened cosmetics and many non-fashion electronics/appliances; Wallapop and eBay ban recalled batteries, weapons/tactical gear, prescription/medical devices, counterfeit luxury goods, and unverified therapeutic claims).

Evaluating every cataloged product by uploading full Terms & Conditions documents (10,000–50,000+ tokens across platforms) on every AI request would burn massive token budgets and add latency. Conversely, having zero automated policy checks exposes the store's marketplace accounts to automated takedowns or permanent bans.

### Solution Overview ("ClauseGuard")
Implement a **Two-Stage, Zero-Waste Advisory Policy Compliance Engine** integrated directly into the existing intake and staging lifecycle:
1. **Per-Platform Policy Knowledge Base & Hybrid URL Sync (`MarketplaceSite` + `PolicyClause`)**:
   - Each `MarketplaceSite` stores an optional `policy_url`, `policy_raw_text` fallback, `policy_content_hash` (SHA-256), and `policy_last_synced_at`.
   - Atomic rules are indexed in `PolicyClause` (seeded out-of-the-box for Wallapop, Vinted, eBay, Milanuncios, and Global/Rápido Pack Storefront) with bilingual (`es`/`en`) titles and descriptions, deterministic `hard_block_keywords`, and cached semantic embedding vectors (`embedding_vector` JSON float array in SQLite).
   - A management command (`python manage.py sync_marketplace_policies`) and Django Admin action fetch configured `policy_url` endpoints (gracefully falling back to `policy_raw_text` or seeded clauses if a platform's anti-bot firewall blocks automated scraping), compare the SHA-256 content hash, and only invoke Gemini to extract/embed clauses when the policy text has changed.
2. **Stage 1: Local Zero-Token Filter & Manual-Edit Guardrail (`<5ms`, `0` LLM tokens)**:
   - Scans `raw_note`, `ai_title`, and `ai_description` against `PolicyClause.hard_block_keywords` and ranks all active clauses using local semantic/lexical similarity to select **only the top 3 relevant clauses** (~150 tokens total instead of 15,000+ tokens).
   - Runs automatically and synchronously inside `Product.save()` whenever text fields change, updating the product's advisory compliance state with zero network latency.
3. **Stage 2: Piggybacked Multimodal Evaluation & Auto-Sanitizing Copywriter**:
   - **At Intake (`identify_intake_product`)**: Piggybacks onto the existing 3-photo Gemini Vision pre-flight call (**0 extra API calls**). Detects both visual hazards (e.g., swollen/damaged lithium batteries, prescription medicines, weapons/airsoft, unsealed cosmetics, counterfeit markings) and note triggers, showing a non-blocking advisory warning on `/intake/`.
   - **At Staging (`generate_product_listing`)**: Injects only the top-3 matched clauses into the existing copywriting prompt (**0 extra API calls**). Gemini **auto-sanitizes** the generated `ai_title` and `ai_description` (avoiding banned medical/therapeutic claims or brand keyword stuffing) while returning a structured compliance verdict (`APPROVED`, `MANUAL_REVIEW`, `REJECTED`), a `0–100` risk score, violated clause citations, a **Per-Platform Compatibility Matrix** (`allowed` / `review` / `prohibited` per site), and token-savings telemetry (`tokens_used` vs. `naive_full_tc_tokens`).
   - **On-Demand Targeted Stage 2 Verification (`/products/<pk>/verify-compliance/`)**: Manager-only POST endpoint that runs Stage 1 + targeted top-3-clause Stage 2 verification (~250 tokens) when a Manager edits listing copy manually and wants a fresh AI compliance check without overwriting their custom title or description.
4. **Strictly Advisory UX**:
   - Never hard-blocks product creation or forces `ProductStatus.BLOCKED`. Displays high-contrast advisory badges on `/intake/`, `/dashboard/` (with a `?compliance=flagged` filter), and a comprehensive **ClauseGuard Compliance & Platform Compatibility Card** on `/products/<pk>/`.

---

## 2. Tech Stack

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database & Vector Cache:** SQLite storing compact float vectors in `PolicyClause.embedding_vector` (`JSONField`) with pure-Python cosine similarity + normalized lexical BM25/token-overlap fallback (zero external vector DB dependencies)
- **AI Integration:** `google-genai` (`gemini-flash-latest` for granular policy rule extraction & pass/fail compliance verification; Gemini Flash for multimodal vision & structured JSON listing generation; `gemini-embedding-001` with deterministic local fallback when offline/testing)
- **Frontend:** Django Templates + Tailwind CSS + Vanilla JS (strictly compliant with OPPO A74 `360×800` & `320×711` low-DPI mobile viewports)
- **Localization:** Bilingual (`es` / `en`) via Django `i18n` and `polib` (`manage.py compile_locales`)

---

## 3. Commands

```powershell
# 1. Lint & Style Check (Ruff)
.venv\Scripts\ruff.exe check .

# 2. Django System Check
.venv\Scripts\python.exe manage.py check

# 3. Create & Apply Database Migrations
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate

# 4. Sync / Seed Marketplace Policies & Embeddings
.venv\Scripts\python.exe manage.py sync_marketplace_policies
.venv\Scripts\python.exe manage.py sync_marketplace_policies --dry-run

# 5. Compile Bilingual Translation Catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# 6. Run Targeted ClauseGuard Test Suite
.venv\Scripts\python.exe manage.py test tests.test_clauseguard_compliance
```

---

## 4. Architecture & Domain Schema (`inventory/models.py`)

### 4.1 Enums (`TextChoices`)

```python
class PolicySeverity(models.TextChoices):
    CRITICAL = "critical", _("Critical (Prohibited)")
    HIGH = "high", _("High Risk (Restricted)")
    MEDIUM = "medium", _("Medium Risk (Conditional / Copy Rule)")


class ComplianceVerdict(models.TextChoices):
    APPROVED = "approved", _("Approved (Safe)")
    MANUAL_REVIEW = "manual_review", _("Manual Review (Warning)")
    REJECTED = "rejected", _("Policy Violation (High Risk)")


class ComplianceStage(models.TextChoices):
    STAGE_1_LEXICAL = "stage_1_lexical", _("Stage 1: Lexical Rule Match (0 Tokens)")
    STAGE_1_SAFE = "stage_1_safe", _("Stage 1: Semantic Safe Short-Circuit (0 Tokens)")
    STAGE_2_PIGGYBACK = "stage_2_piggyback", _("Stage 2: Piggybacked AI Check")
    STAGE_2_TARGETED = "stage_2_targeted", _("Stage 2: Targeted Clause AI Check")
```

### 4.2 `MarketplaceSite` Extensions
Add policy synchronization fields to `MarketplaceSite`:
- `policy_url`: `URLField(max_length=1000, blank=True, default="", validators=[HTTP_URL_VALIDATOR], verbose_name=_("Terms & Conditions URL"))`
- `policy_raw_text`: `TextField(blank=True, default="", verbose_name=_("Terms & Conditions Raw Text (Fallback)"))`
- `policy_content_hash`: `CharField(max_length=64, blank=True, default="", verbose_name=_("Policy Content SHA-256 Hash"))`
- `policy_last_synced_at`: `DateTimeField(null=True, blank=True, verbose_name=_("Policy Last Synced At"))`

### 4.3 New Model: `PolicyClause`
Represents an atomic, indexed Terms & Conditions rule (either global across all platforms when `site=None`, or specific to a `MarketplaceSite`):
- `code`: `CharField(max_length=40, unique=True, db_index=True)` (e.g., `GLB-101`, `WP-201`, `VT-301`, `EB-401`, `ML-501`)
- `site`: `ForeignKey(MarketplaceSite, null=True, blank=True, on_delete=models.CASCADE, related_name="policy_clauses")` (`null=True` means Global / Storefront rule applying to all platforms)
- `category`: `CharField(max_length=80, default="General")` (e.g., `Regulated & Hazardous`, `Medical & Health Claims`, `Counterfeit & IP`, `Weapons & Tactical`, `Platform Category Restriction`, `Hygiene & Cosmetics`, `Deceptive Copy / Keyword Stuffing`)
- `severity`: `CharField(max_length=20, choices=PolicySeverity.choices, default=PolicySeverity.HIGH, db_index=True)`
- `title_es`: `CharField(max_length=200)`
- `title_en`: `CharField(max_length=200, blank=True, default="")`
- `description_es`: `TextField()`
- `description_en`: `TextField(blank=True, default="")`
- `hard_block_keywords`: `JSONField(default=list, blank=True)` (List of lowercase keywords/phrases in ES/EN that deterministically flag the clause in Stage 1 without needing LLM tokens)
- `embedding_vector`: `JSONField(default=list, blank=True)` (Cached float vector for semantic cosine matching)
- `is_active`: `BooleanField(default=True, db_index=True)`
- `updated_at`: `DateTimeField(auto_now=True)`

### 4.4 `Product` Advisory Compliance Fields
Add orthogonal advisory fields to `Product` (never mutating `Product.status`):
- `compliance_status`: `CharField(max_length=20, choices=ComplianceVerdict.choices, default=ComplianceVerdict.APPROVED, db_index=True)`
- `compliance_risk_score`: `PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])`
- `compliance_stage`: `CharField(max_length=30, choices=ComplianceStage.choices, default=ComplianceStage.STAGE_1_SAFE)`
- `compliance_report`: `JSONField(default=dict, blank=True)` storing structured trace:
  ```json
  {
    "summary": "Safe for Wallapop and Storefront; restricted on Vinted (non-fashion appliance).",
    "matched_clauses": [
      {
        "code": "VT-302",
        "site_slug": "vinted",
        "site_name": "Vinted",
        "title": "Small Home Appliances & Non-Fashion Electronics",
        "severity": "high",
        "excerpt": "freidora de aire",
        "explanation": "Vinted catalog rules restrict non-wearable kitchen appliances."
      }
    ],
    "sanitized_actions": [
      "Removed unverified therapeutic claim per GLB-104."
    ],
    "platform_matrix": {
      "rapido-pack": {"status": "approved", "label": "Allowed", "clauses": []},
      "wallapop": {"status": "approved", "label": "Allowed", "clauses": []},
      "vinted": {"status": "manual_review", "label": "Restricted (VT-302)", "clauses": ["VT-302"]},
      "ebay": {"status": "approved", "label": "Allowed", "clauses": []},
      "milanuncios": {"status": "approved", "label": "Allowed", "clauses": []}
    },
    "telemetry": {
      "top_k_clauses_sent": 3,
      "tokens_used": 145,
      "naive_baseline_tokens": 12000,
      "tokens_saved_percent": 98.8
    }
  }
  ```
- `compliance_checked_at`: `DateTimeField(null=True, blank=True)`

---

## 5. Service Architecture (`inventory/services/compliance_service.py`, `policy_sync_service.py`, `policy_clauses_seed.py`)

### 5.1 Pre-Seeded Marketplace Policy Clauses
`ensure_default_policy_clauses()` seeds 12 realistic, high-value bilingual clauses covering:
- **Global / All Platforms (`site=None`)**:
  - `GLB-101` (`CRITICAL`): Weapons, Ammunition, Replica Firearms, Airsoft/Bladed Weapons (`armas`, `pistola`, `airsoft`, `navaja automática`, `munición`, `taser`, `weapon`, `firearm`).
  - `GLB-102` (`CRITICAL`): Prescription Medicines, Drugs, Supplements & Medical Devices (`medicamento`, `receta médica`, `antibiótico`, `anabolizantes`, `prescription`, `steroids`, `viagra`).
  - `GLB-103` (`CRITICAL`): Counterfeit Goods, Replicas, Imitations & IP Infringement (`réplica`, `imitación`, `falso`, `clon exacto`, `1:1`, `fake`, `counterfeit`, `bootleg`, `pirata`).
  - `GLB-104` (`MEDIUM`): Unverified Medical/Therapeutic Claims & Brand Keyword Stuffing (`cura el dolor`, `tratamiento médico`, `milagroso`, `tipo zara nike adidas`, `cures pain`, `medical cure`).
  - `GLB-105` (`HIGH`): Recalled, Swollen/Damaged Lithium Batteries & Hazardous Materials (`batería hinchada`, `inflamable`, `explosivo`, `gas butano`, `airbag`, `swollen battery`, `hazardous`).
  - `GLB-106` (`HIGH`): Digital Accounts, Pirated Software, Modchips & Lockpicks (`cuenta netflix`, `licencia pirateada`, `ganzúa`, `pirated`, `hacked account`).
- **Platform-Specific Clauses (`site` linked to Wallapop, Vinted, eBay, Milanuncios)**:
  - `VT-201` (Vinted, `HIGH`): Opened/Used Cosmetics, Perfumes & Personal Hygiene Items (`perfume empezado`, `maquillaje usado`, `cosmético abierto`, `used makeup`, `opened perfume`).
  - `VT-202` (Vinted, `MEDIUM`): Large Appliances, Power Tools & Automotive Parts Prohibited on Vinted (`lavadora`, `frigorífico`, `radial`, `taladro percutor`, `neumático`, `carburador`, `washing machine`, `power drill`).
  - `WP-301` (Wallapop, `HIGH`): Tobacco, Vapes, E-Cigarettes & Alcohol (`vaper`, `cigarrillo electrónico`, `shisha`, `cachimba`, `botella de vino`, `licor`, `vape`, `e-liquid`).
  - `EB-401` (eBay, `HIGH`): OEM Software Recovery Discs, Catalytic Converters & Airbag Modules (`catalizador`, `módulo airbag`, `catalytic converter`, `airbag module`).
  - `ML-501` (Milanuncios, `MEDIUM`): Animals, Live Plants/Seeds & Regulated Agricultural Chemicals (`fitosanitario`, `herbicida profesional`, `mascota`, `cachorro`).

### 5.2 Stage 1: Fast Local Filter (`evaluate_stage1_local`)
1. Normalizes product text (`raw_note`, `ai_title`, `ai_description`, `category`).
2. Checks `hard_block_keywords` using word-boundary-aware matching.
3. Computes semantic/lexical similarity against all active `PolicyClause` rows (using cached `embedding_vector` cosine similarity when available + weighted token overlap).
4. Selects the **top 3 candidate clauses** (`top_k=3`) and builds the per-platform compatibility matrix and token telemetry (`naive_baseline_tokens = 12000` vs `tokens_used = 0` for Stage 1).
5. When invoked from `Product.save()` on manual edits, updates `compliance_status`, `compliance_risk_score`, `compliance_stage`, and `compliance_report` in `<5ms` with zero external API calls.

### 5.3 Stage 2: Piggybacked & Targeted AI Evaluation (Zero-Reason Pass/Fail)
1. **Piggybacked on `identify_intake_product` (`ai_service.py`)**:
   - Injects ONLY the top-3 Stage 1 clauses (~150 tokens) into the intake prompt (**0 extra API calls**) and extends `IntakePreflightSchema` with:
     - `compliance_passed`: `bool` (`true` if safe, `false` if any clause triggered)
     - `violated_clause_codes`: `list[str]` (exact violated clause codes, e.g. `["VT-201"]`, without asking Gemini to generate explanations)
2. **Piggybacked on `generate_product_listing` (`ai_service.py`)**:
   - Runs Stage 1 first to fetch the top 3 relevant `PolicyClause` records (~150 tokens).
   - Injects those 3 clauses into the copywriting prompt with explicit instructions to:
     1. **Auto-sanitize** `title` and `description` so they do not make prohibited therapeutic claims or keyword-stuff unrelated brands.
     2. Populate compact compliance fields in `ProductListingSchema` (`compliance_passed`, `violated_clause_codes`, `sanitized_note`), avoiding reason/explanation output tokens.
   - `merge_stage2_compliance_result()` deterministically derives verdict, risk score, localized rule titles/descriptions, and the Per-Platform Compatibility Matrix from the local `PolicyClause` DB records.
3. **Standalone Targeted Verification (`verify_product_compliance_ai`)**:
   - Triggered via `POST /products/<pk>/verify-compliance/` (`product_verify_compliance_view`).
   - Sends *only* the product text and top-3 matched clauses to `gemini-flash-latest`, requesting strictly pass/fail (`passed`: `bool`) + `violated_clause_codes` (zero explanation output tokens). Exact rule citations and descriptions are populated locally from `PolicyClause`, and targeted `passed=True` verification clears verified Stage 1 keyword false-positives.
4. **Granular SSRF-Protected Policy Extraction (`sync_site_policy` in `policy_sync_service.py`)**:
   - Validates remote URLs (and HTTP redirects) against private/loopback/metadata IPs, enforces `text/*` responses, only persists `policy_content_hash` when Gemini extraction succeeds, deactivates obsolete auto-synced rules on re-sync, and uses `gemini-flash-latest` without an artificial 8-rule cap across up to 60,000 characters.

---

## 6. User Interface & Mobile Ergonomics (OPPO A74 `360×800` & `320×711`)

1. **Intake Screen (`/intake/`, `intake.html`)**:
   - Inside `#aiIdentifyBanner`, when `compliance_verdict != 'approved'` or `compliance_flags` is non-empty, renders an accessible advisory alert (`#intakeComplianceAlert`) displaying the risk score badge and detected visual/note policy warnings.
   - Persists initial Stage 1 compliance check upon product creation in `product_intake_view`.
2. **Catalog Dashboard (`/dashboard/`, `dashboard.html`)**:
   - Secondary Filter Bar includes a compact compliance filter pill/toggle (`?compliance=flagged`) showing the count of products requiring review (`compliance_status__in=['manual_review', 'rejected']`).
   - Product cards display a compact badge when flagged (`🛡️ Review · 65` in amber or `🛡️ Policy Risk · 90` in rose) using `flex-wrap min-w-0` so narrow `320px` screens never overflow horizontally.
3. **Product Detail Workspace (`/products/<pk>/`, `product_detail.html`)**:
   - Dedicated **ClauseGuard Policy Compliance Card** (`#clauseGuardCard`):
     - Header with current verdict badge (`✅ Approved`, `⚠️ Manual Review`, `🚫 Policy Violation`), numerical Risk Score (`0–100`), resolution stage (`Stage 1: 0 Tokens` vs `Stage 2: Top-3 Clauses`), and Token Savings indicator (`Saved 98.8% tokens vs Full T&C`).
     - **Per-Platform Compatibility Matrix**: Wrapping flex pills showing status for `Rápido Pack`, `Wallapop`, `Vinted`, `eBay`, and `Milanuncios`.
     - **Matched / Violated Clauses List**: Displays clause code (`VT-202`), severity, localized title, matched excerpt, and AI explanation/sanitization note.
     - **Manager Action**: `🛡️ Verify Compliance` POST button (`/products/<pk>/verify-compliance/`) to re-run Stage 1 + targeted Stage 2 verification at any time.
   - Next to each platform in the **Marketplace Links Card**, displays a subtle compatibility indicator if that specific platform has a flagged clause.
4. **Django Admin (`inventory/admin.py`)**:
   - `PolicyClauseAdmin` registered in `manager_admin_site` with site filter, severity badges, keyword search, and bulk action **"Re-compute clause embeddings"**.
   - `MarketplaceSiteAdmin` extended with `policy_url`, `policy_raw_text`, `policy_last_synced_at`, and bulk action **"Sync & extract policy clauses from URL / text"**.
