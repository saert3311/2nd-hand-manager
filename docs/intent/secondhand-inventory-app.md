# Statement of Intent: Secondhand Inventory & Staging App

- **Outcome:** A lightweight Django inventory intake and staging app where an assistant snaps photos and notes in the field, multimodal vision AI generates marketplace-ready titles and descriptions on demand, and you review inventory, download assets, and track sales status.
- **User:** Store manager/lister (reviewing items, triggering AI, downloading assets, tracking sales) and sourcing assistant / User A (streamlined mobile intake form for quick photo uploads and raw notes).
- **Why now:** Eliminate friction from manual phone-to-desktop photo transfers and slash time spent manually drafting titles and descriptions for external marketplaces.
- **Success:** User A can catalog an item with multiple photos and a quick note in seconds; manager can click a button to generate AI copy, download product photos easily, and update sale price and sold status from a central dashboard.
- **Constraint:** Standard Django application using Django's built-in auth/admin for user management, standard server-rendered views/templates, and a simple multimodal vision API key (e.g., Gemini).
- **Out of scope:** Direct marketplace API auto-posting (e.g., eBay/Vinted/Wallapop APIs), public buyer-facing storefront or payment processing, native mobile apps, and complex accounting/profit margin calculations.
