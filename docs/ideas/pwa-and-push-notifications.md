# Installable PWA & Web Push Notification Foundation

## Problem Statement
How might we turn **2ndHand Staging** into an installable, native-feeling mobile app for both Assistants and Managers—while establishing a zero-cache, standards-based Web Push foundation so urgent workflow bottlenecks (Clarification Doubts, new Drafts, and Price Pending items) reach the right person's device immediately?

## Recommended Direction
Implement a **Zero-Cache Pass-Through PWA** paired with a **Standards-Based VAPID Web Push Foundation (`pywebpush`)** and an environment-controlled live signal trigger (`PUSH_NOTIFICATIONS_LIVE_SIGNALS`).

On the frontend, expose a localized `/manifest.json`, custom PWA app icons (`192x192`, `512x512`, maskable, and Apple Touch Icon), and a root-scoped `/sw.js`. The Service Worker uses a network pass-through `fetch` listener (satisfying browser installability criteria without risking stale Django CSRF tokens or cached inventory states) and handles `push` and `notificationclick` events—focusing an existing app window or opening the target deep-link URL (`/products/<id>/` or `/dashboard/?status=price_pending`), while using notification `tag` keys to collapse burst alerts cleanly and `navigator.setAppBadge` when supported.

On the backend, introduce a `PushSubscription` model linked to `User` (storing `endpoint`, `p256dh`, `auth`, `user_agent`, and `is_active`), VAPID key configuration (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`) with a management command (`generate_vapid_keys`), authenticated subscribe/unsubscribe/test JSON endpoints, a navbar and mobile drawer **"🔔 Notifications"** toggle button, and a `inventory/services/push_service.py` module providing `send_push_to_user()` and `send_push_to_group()` helpers (with automatic HTTP 404/410 dead-subscription pruning).

Additionally, wire a `.env` feature flag (`PUSH_NOTIFICATIONS_LIVE_SIGNALS=True|False`) into Django signals so live push alerts for Clarification Q&A (Manager asks doubt → Assistants notified; Assistant answers → Managers notified) and Intake/Lifecycle bottlenecks (new product enters `DRAFT` or transitions to `PRICE_PENDING` → Managers notified) can be toggled via environment configuration.

## Key Assumptions to Validate
- [x] Root-scoped `/sw.js` registers cleanly with scope `/` across Chrome, Edge, Firefox, and Safari without interfering with WhiteNoise static file serving.
- [x] Subscribing from the navbar/drawer toggle persists a valid `PushSubscription` record and supports multiple devices per user (e.g., a Manager's laptop + phone).
- [x] `push_service.py` gracefully handles missing VAPID keys, disabled `.env` flags, network timeouts, and HTTP `410 Gone` expired endpoints without ever blocking or crashing a Django request.

## MVP Scope
- **In Scope:**
  - Web App Manifest (`/manifest.json`), PWA meta tags (`theme-color`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`), and generated PWA icons (`192x192`, `512x512`, Apple touch icon).
  - Root-scoped pass-through Service Worker (`/sw.js`) with `install`, `activate`, `fetch` (pass-through), `push` (JSON payload + OS app badging), and `notificationclick` (deep-link navigation).
  - `PushSubscription` model, migration, and Django Admin registration (including a "Send Test Notification" admin action).
  - VAPID settings and `PUSH_NOTIFICATIONS_LIVE_SIGNALS` flag in `config/settings.py` and `.env.example` + `generate_vapid_keys` management command.
  - Subscribe / Unsubscribe / Test JSON API endpoints (`/api/push/subscribe/`, `/api/push/unsubscribe/`, `/api/push/test/`) and UI toggle button in desktop navbar & mobile drawer (with iOS "Add to Home Screen" detection hint).
  - `inventory/services/push_service.py` helper functions + signal hooks (guarded by `PUSH_NOTIFICATIONS_LIVE_SIGNALS`) for Clarification Doubts Q&A and Draft/Price Pending lifecycle bottlenecks.

## Not Doing (and Why)
- **Offline HTML/Asset Caching in Service Worker** — Caching Django HTML templates breaks CSRF tokens on POST forms and serves stale inventory states; pass-through keeps behavior 100% predictable.
- **Offline IndexedDB Photo Upload Queue** — High complexity for rare total-blackout scenarios; Gemini AI preflight identification requires live connectivity anyway.
- **External Cloud Push Providers (Firebase FCM / OneSignal)** — Introduces external vendor lock-in and third-party tracking scripts when standard VAPID (`pywebpush`) works natively across Android, Desktop, and iOS 16.4+.
- **Automatic Page-Load Permission Prompts** — Calling `Notification.requestPermission()` without a user gesture is penalized/blocked by browsers and annoys users; we strictly trigger on user click of the notification toggle.

## Resolved Decisions
- **Target Audience:** Both Assistants (mobile intake & answering doubts) and Managers (staging & reviewing).
- **Service Worker Strategy:** Minimal pass-through Service Worker strictly for PWA installability and Push Notifications (no offline caching).
- **Environment Trigger:** Include `PUSH_NOTIFICATIONS_LIVE_SIGNALS` in `.env` / `config/settings.py` to control automatic signal-driven push dispatch.
