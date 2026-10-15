# Product Requirements Document (PRD): Responsive Mobile Navigation & Collapsible Sandwich Menu

## 1. Executive Summary
Provide a clean, uncluttered, and responsive mobile navigation experience for the 2ndHand Staging web application. 

Currently, on viewports under 768px (such as iPhone 14/15, Android phones at 360–390px), the top navigation bar displays multiple horizontal items simultaneously: the brand logo and badge, the bilingual language switcher (EN / ES), the Intake shortcut button, the Dashboard link, the doubts attention badge, and the Sign Out button. This causes horizontal crowding, wrapping, micro-touch targets, and visual clutter on mobile warehouse devices.

This feature introduces a responsive collapsible mobile navigation system ("sandwich / hamburger menu") on screens `< md` (768px), while keeping the full horizontal navigation bar on desktop devices (`≥ md`). The mobile top bar becomes minimal and uncluttered (Logo on the left, high-priority notification pill in the center/right if pending doubts exist, and a prominent 44×44px hamburger toggle on the right). Tapping the sandwich icon smoothly opens an accessible mobile drawer panel containing organized navigation links, user identity and role badges, the language switcher, and logout actions.

---

## 2. Problem Statement
1. **Severe Mobile Header Crowding:** The current header packs 6 distinct interactive widgets into a single 64px-high bar without a mobile breakpoint collapse. On devices with screens <= 390px width, text wraps, buttons shrink below comfortable touch target guidelines, and visual noise distracts sourcing staff.
2. **Accidental Clicks Near Sign Out:** On narrow screens, the "Sign Out" button sits directly adjacent to the primary navigation buttons with narrow spacing, leading to accidental logouts during active warehouse intake.
3. **Language Switcher Usability:** The language switcher buttons (`🇬🇧 EN` / `🇪🇸 ES`) take up ~110px of horizontal width in the main bar on mobile, competing with essential workflow links.
4. **Sub-optimal Mobile Touch Targets:** Micro-padding on mobile links violates WCAG 2.1 AA recommended 44×44px minimum touch target dimensions.
5. **Inconsistent Navigation Hierarchy:** Secondary management links (like Django Admin for managers) are completely hidden on smaller screens (`hidden md:inline`) with no mobile access mechanism.

---

## 3. User Personas & Scenarios

### Persona 1: Field Sourcing Assistant (User A)
- **Device:** iPhone 14 / Samsung Galaxy (390px mobile viewport).
- **Scenario:** The assistant is in a secondhand market or warehouse uploading photos. They want the top bar to be sleek and distraction-free, with immediate visual focus on their current work. Tapping the top-right sandwich button gives them instantaneous, one-thumb access to the catalog dashboard, their active language switch, and any pending manager doubts.

### Persona 2: Store Manager / Lister (User B)
- **Device:** Mobile phone when reviewing on the go, Desktop PC in the office.
- **Scenario (Desktop):** The manager sees the full, uncollapsed top navigation bar with wide spacing, full user details, language switcher, and direct links to Intake, Dashboard, Doubts, and Admin.
- **Scenario (Mobile):** When checking inventory on a phone, the manager can tap the sandwich menu and access the Django Admin link (which was previously inaccessible on mobile), without cluttering the mobile interface.

---

## 4. Scope & Technical Architecture

### 4.1 Responsive Breakpoint Architecture
- **Breakpoint:** Tailwind `md:` (768px).
- **Desktop (`≥ 768px` / `md:`):**
  - Mobile menu toggle button is hidden (`md:hidden`).
  - Standard horizontal navigation and language switcher are visible (`hidden md:flex`).
  - User avatar/username and logout button render inline.
- **Mobile (`< 768px`):**
  - Standard horizontal navigation links and inline language switcher are hidden (`hidden md:flex`).
  - Top bar renders:
    1. **Left:** App Brand (`📦 2ndHand` + `Staging` pill).
    2. **Right:** 
       - Optional urgent badge: If `pending_clarifications_count > 0`, display a compact attention pill (`❓ {{ pending_clarifications_count }}`) in the top bar for immediate notice.
       - Mobile Menu Toggle Button (`#mobile-menu-button`): Minimum 44×44px touch target, displaying an animated SVG hamburger icon (3 bars) when closed, and an "✕" close icon when open.
  - Collapsible Mobile Drawer Panel (`#mobile-menu`):
    - Positioned directly below the sticky header.
    - Features clean border-b, backdrop blur / elevated card styling (`bg-white border-b border-slate-200 shadow-lg`).
    - Disappears smoothly when closed (`hidden`).

### 4.2 Mobile Menu Drawer Structure
When expanded, the mobile menu presents a clean vertical hierarchy:
```
┌──────────────────────────────────────────────┐
│ 📦 2ndHand Staging            ❓ 2   [ ✕ ]   │  <- Top Bar (Sticky)
├──────────────────────────────────────────────┤
│ 👤 Conectado como: assistant (Asistente)     │  <- User Profile Card
├──────────────────────────────────────────────┤
│ 📷 Nueva Entrada                             │  <- Primary Workflow Action (Highlighted)
│ 📊 Catálogo / Dashboard                      │  <- Secondary Action
│ ❓ Dudas pendientes (2)                      │  <- Urgent Attention Action
│ ⚙️ Panel de Administración                    │  <- (Managers only)
├──────────────────────────────────────────────┤
│ 🌐 Idioma: [ 🇬🇧 English ] [ 🇪🇸 Español ]     │  <- Full-width segmented language toggle
├──────────────────────────────────────────────┤
│ 🚪 Cerrar Sesión                             │  <- High-contrast logout button
└──────────────────────────────────────────────┘
```

### 4.3 Accessibility & Keyboard Interaction Contract
- **ARIA Attributes:**
  - `#mobile-menu-button`: `aria-expanded="false"`, `aria-controls="mobile-menu"`, `aria-label="{% trans 'Open menu' %}"`.
  - Dynamically updates `aria-expanded="true"` and label to `"Close menu"` upon opening.
  - `#mobile-menu`: `role="region"` or `role="navigation"`, `aria-label="{% trans 'Mobile navigation' %}"`.
- **Keyboard Navigation:**
  - Pressing `Escape` while the menu is open immediately closes the drawer and restores focus to `#mobile-menu-button`.
  - Tapping outside the mobile menu (click outside) automatically closes the drawer.
  - Resizing the browser window to `≥ md:` automatically resets the menu to closed state.

---

## 5. Non-Functional Requirements
- **WCAG 2.1 AA Compliance:** Minimum 44×44px touch targets for the hamburger button and all drawer links; minimum 4.5:1 text color contrast against the white background.
- **Zero Heavy Dependencies:** Written in lightweight vanilla JavaScript (~30 lines of code) with no external libraries (alpine, react, etc.).
- **Smooth Visual Polish:** Crisp SVG icons, subtle transition states, consistent Tailwind slate/emerald design tokens matching the existing application aesthetic.
- **Backward Compatibility:** All existing backend tests checking for `badge-pending-clarifications`, `set_language`, `Sign Out`, and translation tokens continue to pass without regression.

---

## 6. Success Metrics & Acceptance Criteria
1. On viewports `< 768px`, the top header contains only the brand logo, optional doubts attention pill, and the sandwich toggle button.
2. Clicking/tapping the sandwich button toggles the mobile drawer open/closed with smooth SVG icon switching (☰ to ✕).
3. The drawer contains clearly labeled links for Intake, Dashboard, Doubts, Admin (for managers), Language Switcher, and Sign Out.
4. Tapping outside the drawer or pressing the `Escape` key closes the menu.
5. On desktop viewports (`≥ 768px`), the sandwich button is hidden and the standard horizontal menu is displayed.
6. All automated unit and browser tests pass with 100% green.
