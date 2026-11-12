# ClauseGuard — Cost-Optimized Multi-Platform Policy Compliance

## Problem Statement
How might we alert Sourcing Assistants at intake and Store Managers during staging when a product risks violating platform-specific Terms & Conditions (Wallapop, Vinted, eBay, Milanuncios, Rápido Pack), while keeping policies synced from platform URLs and spending near-zero extra tokens per product?

## Recommended Direction
Implement **ClauseGuard**, a hybrid two-stage advisory compliance engine integrated directly into the existing 2ndHand Staging Hub workflow:

1. **Per-Platform Clause Knowledge Base & Hybrid URL Sync (`MarketplaceSite` + `PolicyClause`)**:
   Extend `MarketplaceSite` with `policy_url`, `policy_raw_text`, `policy_content_hash`, and `policy_last_synced_at`. Store atomic rules in `PolicyClause` (seeded with default Spanish/English rules for Wallapop, Vinted, eBay, Milanuncios, and Storefront, plus `hard_block_keywords` and cached `gemini-embedding-001` vectors in SQLite). A management command (`sync_marketplace_policies`) and Admin action fetch the URL (or pasted text), check if the SHA-256 hash changed, and use Gemini to extract updated clauses and embeddings only when rules change.

2. **Two-Stage Zero-Waste Evaluation Pipeline (`inventory/services/compliance_service.py`)**:
   - **Stage 1 (Local <5ms, 0 LLM tokens):** Scans product notes/title/description against `hard_block_keywords` and ranks `PolicyClause` items via local vector/lexical similarity to select only the **top 3 candidate clauses** (~150 tokens instead of 15,000+ tokens). Runs automatically on manual `Product.save()` edits to keep advisory status up to date for free.
   - **Stage 2 (Piggybacked Multimodal AI + Auto-Sanitizing Copywriter):**
     - **Intake Pre-Flight (`identify_intake_product`):** Piggybacks visual + text compliance checks onto the existing 3-photo Gemini Vision call, warning the Assistant immediately if photos show restricted items (e.g., recalled/swollen batteries, unsealed cosmetics, counterfeit markings, weapons/tactical gear, prescription products).
     - **Listing Generation (`generate_product_listing`):** Injects only the top-3 matched clauses into the existing copywriting prompt so Gemini **auto-sanitizes** the generated copy (avoiding prohibited medical claims or brand keyword stuffing) and outputs a structured compliance verdict (`APPROVED`, `MANUAL_REVIEW`, `REJECTED`), a `0–100` risk score, violated clause citations, and a **Per-Platform Compatibility Matrix** (e.g., allowed on Wallapop/In-Store, restricted on Vinted).
     - **On-Demand Re-Verify Endpoint (`/products/<pk>/verify-compliance/`):** Allows Managers to trigger a targeted Stage 1 + Stage 2 check (~250 tokens) after manual edits without overwriting their custom listing copy, displaying token savings (`Tokens Used` vs. `Naive Full-T&C Baseline`).

## Key Assumptions to Validate
- [ ] **Platform URLs vs. Anti-Bot Walls:** Validate that our policy sync gracefully falls back to Admin-pasted `policy_raw_text` and pre-seeded clauses when a marketplace blocks automated HTTP scraping.
- [ ] **Zero-Latency Manual Saves:** Ensure `Product.save()` only runs local Stage 1 lexical/cached-vector matching (<5ms) and never blocks on external API requests.
- [ ] **OPPO A74 (`320×711` / `360×800`) Readability:** Verify that the new Compliance Advisory badge on `/dashboard/`, pre-flight warning on `/intake/`, and Platform Compatibility Matrix on `/products/<pk>/` wrap cleanly with zero horizontal overflow.

## MVP Scope
- **In Scope:**
  - `MarketplaceSite` policy sync fields + `PolicyClause` model with bilingual (`es`/`en`) fields, `hard_block_keywords`, and SQLite JSON embedding storage.
  - Default seeded clauses for Wallapop, Vinted, eBay, Milanuncios, and Rápido Pack Storefront.
  - `Product` advisory compliance fields (`compliance_status`, `compliance_risk_score`, `compliance_stage`, `compliance_report` JSON with violated clauses, sanitized notes, platform matrix, and token savings telemetry).
  - Stage 1 local filter + Stage 2 piggybacking on `identify_intake_product` and `generate_product_listing` + standalone `product_verify_compliance_view`.
  - Advisory UI badges on `/intake/`, `/dashboard/` (plus `?compliance=flagged` filter), and the ClauseGuard Compliance & Platform Matrix card on `/products/<pk>/`.
- **Not Doing (and Why):**
  - **Hard-blocking product saves or auto-locking status to `BLOCKED`** — Compliance is strictly **advisory** so false positives never halt warehouse intake or override Manager judgment.
  - **External Vector Database (Pinecone / Qdrant / pgvector)** — We have <500 policy clauses; computing cosine similarity over JSON float arrays in SQLite/Python takes <2ms with zero infrastructure cost.
  - **Sending full Terms & Conditions documents in product prompts** — Defeats the core unit-economics goal; only the top-K (max 3) matched clauses are ever sent to Stage 2.

## Open Questions (Resolved)
- **Trigger Points:** Both Intake pre-flight (Assistant early warning) and Staging AI Generation / Manual Edits (Manager advisory gate).
- **Policy Sources:** Hybrid per-platform `policy_url` + `policy_raw_text` fallback on `MarketplaceSite` with atomic `PolicyClause` rows.
- **Enforcement Mode:** Strictly advisory (`APPROVED`, `MANUAL_REVIEW`, `REJECTED` badge + `0–100` risk score + per-platform matrix); Manager retains final authority.
- **Token Strategy:** Stage 1 local filter + Stage 2 piggybacked on existing Gemini calls (0 extra API calls during normal flow).
