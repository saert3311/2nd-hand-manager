# Idea: Out-of-Sync Product Web Push Notifications

## Context & Motivation
In Phase 33, we introduced platform synchronization tracking (`needs_platform_sync`) to track when an already published product undergoes post-publication modifications (price changes, copywriting edits, photo additions/deletions, cover photo reordering, or new clarification notes).

When these modifications occur, the product becomes "out of sync" (`needs_platform_sync = True`), meaning its external listings on marketplaces (e.g. Wallapop, Vinted, Milanuncios) are stale compared to the hub's catalog truth.

Currently:
1. The Product Detail workspace displays an amber warning banner (`#platformSyncBanner`) with a 1-click clearance action (`✅ Marcar plataformas como actualizadas`).
2. The Catalog Dashboard provides a sub-filter tab (`?status=published&sync=out_of_sync`) and displays pulsing amber badges (`⚠️ Actualizar plataformas`) on product cards.

However, store managers who are off-duty, managing physical store operations, or not actively monitoring the dashboard have no real-time push mechanism alerting them that an item requires external platform updates. This delay can lead to discrepancies between store prices/descriptions and marketplace listings.

## The Idea
Dispatch an immediate, actionable Web Push notification to all active Store Managers (`ROLE_MANAGER`) whenever a published product transitions into an out-of-sync state (`needs_platform_sync: False -> True`).

### Core Requirements:
1. **Targeted Delivery**: Web Push delivered to all active subscriptions of the store managers group (`ROLE_MANAGER` + active staff/superusers) using VAPID and `pywebpush`.
2. **State Transition Guard (Anti-Spam)**: Only trigger the notification when `needs_platform_sync` transitions from `False` to `True`. Subsequent edits while the item is already flagged out-of-sync must not dispatch redundant notifications.
3. **Actionable Deep-Linking**: The push notification payload contains the direct URL `/products/<pk>/`, taking the manager straight to the product staging workspace where the amber warning banner and 1-click clearance button reside.
4. **Browser Tag Collapse**: Use tag `product-out-of-sync-<pk>` so notifications for the same product replace each other in the OS notification drawer.
5. **Configurable Live Signals**: Respect `PUSH_NOTIFICATIONS_LIVE_SIGNALS` setting so notifications can be enabled/disabled per environment and isolated during tests.
