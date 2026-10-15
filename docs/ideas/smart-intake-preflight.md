# Smart Intake Pre-flight: On-Demand Item Identification & Advisory Guidance

## Problem Statement
Assistants cataloging items in the field sometimes miss crucial details (e.g. unreadable size tags, unnoticed seam tears, hidden serial numbers) that managers later have to request via clarifications. How might we give assistants an instant AI second-opinion before submission without adding friction?

## Recommended Direction
Add a lightweight, on-demand **"🔍 Identificar producto"** action to the mobile intake form:
1. **On-Demand Vision Analysis:** Once photos are chosen, the assistant can tap "Identificar producto". The client submits the photos to a fast endpoint backed by `gemini-2.5-flash`.
2. **Structured Detection:** Gemini returns:
   - Identified item name (Brand + Category + Model).
   - Key attributes detected (color, material, style).
   - **Actionable Missing Info Checklist** (e.g., *"Tag with garment size is not visible"*, *"Underside wear not shown"*).
3. **Non-Blocking Advisory Banner:** A friendly notification banner appears above the notes field highlighting suggested details to check. The assistant can quickly note the size in `raw_note` or snap an extra photo while the garment is in hand.
4. **Optional Intake Price Field:** Add an optional `sale_price` (€) field to `ProductIntakeForm` so items with known fixed prices can be priced on the spot.

## Key Assumptions to Validate
- [ ] Assistants find 2-second on-demand AI identification helpful rather than intrusive.
- [ ] Downscaling photos on the client before sending to `/identify/` provides accurate vision results while staying under 2 seconds on mobile data.
- [ ] Intake-stage advisory checks measurably decrease `awaiting_info` status flags downstream.

## MVP Scope (In)
1. **Form Enhancement:** Add optional `sale_price` (€) to `ProductIntakeForm` and `intake.html`.
2. **Identify Action & Endpoint:**
   - Dedicated AJAX endpoint (`POST /inventory/intake/identify/`).
   - Pydantic schema returning `identified_title`, `detected_specs`, and `missing_info_tips`.
3. **Intake UI Feedback:**
   - "Identificar producto" button enabled once ≥1 photo is selected.
   - Loading state (spinner / "Analizando fotos...").
   - Non-blocking advisory alert banner displaying tips with a one-click *"Añadir a notas"* shortcut.
4. **Graceful Fallbacks:** If the AI call fails or times out, the assistant can continue and submit normally with zero disruption.

## Not Doing (and Why)
- **Automatic Scan on Photo Selection:** Scanning automatically on every photo picker change burns unnecessary API tokens and creates UI jumping while assistants are selecting multiple photos.
- **Strict Upload Blocker:** We will NOT block the user from saving if info is missing. Speed of intake is paramount; warnings must remain strictly advisory.
- **AI Price Suggestions during Intake:** Kept as a simple, manual optional field as requested, leaving market valuation logic to the staging/manager phase.

## Open Questions
- Should the identified title automatically populate the notes field if `raw_note` is currently empty?
