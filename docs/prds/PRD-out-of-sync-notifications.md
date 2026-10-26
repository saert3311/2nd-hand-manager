# PRD: Out-of-Sync Product Web Push Notifications (Phase 35)

## 1. Executive Summary & Objective

In second-hand multi-channel commerce, inventory is simultaneously listed on external resale marketplaces (e.g., Wallapop, Vinted, Milanuncios, eBay) while physical store operations continue. In Phase 33, we introduced platform synchronization tracking (`needs_platform_sync`) to track whenever an already published product undergoes price changes, copywriting modifications, photo additions/deletions, primary photo reordering, or new clarification notes.

Currently, the application displays an amber warning banner on the Product Detail workspace (`/products/<pk>/`) and offers dashboard sub-filtering (`?status=published&sync=out_of_sync`) with live badges. However, managers are not alerted in real time when products become out of sync. If a manager is not actively browsing the dashboard or detail workspace, price drops or image updates may languish unpropagated to external marketplaces, risking sales at outdated prices or buyer disputes.

### Primary Objectives:
1. **Real-Time Notification Delivery**: Automatically dispatch an encrypted Web Push notification via VAPID and `pywebpush` to all active Store Managers (`ROLE_MANAGER` + active staff/superusers) the moment a published product transitions to out of sync (`needs_platform_sync: False -> True`).
2. **State Transition Guard (Anti-Spam)**: Ensure notifications trigger strictly on state edge transition (`False -> True`). Subsequent updates while `needs_platform_sync` remains `True` must not trigger repeated alerts.
3. **Actionable Deep-Linking**: Link directly to `/products/<pk>/` so managers can tap the push notification and immediately land on the workspace with the `#platformSyncBanner` and the 1-click clearance button (`✅ Marcar plataformas como actualizadas`).
4. **Browser Notification Collapse**: Tag the notification payload with `product-out-of-sync-<pk>` to collapse repeated alerts for the same item in mobile OS notification drawers.
5. **Configurable Environment Gating**: Respect `PUSH_NOTIFICATIONS_LIVE_SIGNALS` to ensure notification dispatch can be enabled or suppressed across development, testing, staging, and production environments.
6. **Bilingual Localization & Comprehensive Test Suite**: Provide full Spanish and English translation coverage and 100% automated test verification.

---

## 2. User Stories & Core Use Cases

### User Story 1: Manager Adjusting Price on a Published Jacket
*As a store manager reviewing slow-moving published inventory, I lower the sale price of a vintage Schott leather jacket from €180 to €150 in the product detail view. As soon as I save the change, the jacket's `needs_platform_sync` turns `True`. A Web Push notification is dispatched to all store managers with the message: "⚠️ Producto desincronizado: Chaqueta Schott Vintage — Cambios detectados en producto publicado. Se requiere actualizar las plataformas externas." Clicking the notification opens the product detail page directly.*

### User Story 2: Assistant Adding an Important Note Post-Publication
*As a sourcing assistant inspecting physical inventory in the warehouse, I notice a minor scuff on the collar of an already published trench coat. I add a clarification note: "Pequeño rasguño en el cuello interior". Because the product is published, this clarification flags `needs_platform_sync = True`. Store managers immediately receive a Web Push notification alerting them that the product requires updating on external marketplaces.*

### User Story 3: Anti-Spam Transition Protection
*As a store manager making several successive photo adjustments on an already out-of-sync product (uploading 2 photos, reordering cover, then correcting a typo in the title), the system sends a notification only on the initial change that made the product out of sync (`False -> True`). Successive edits while `needs_platform_sync` is already `True` do not flood managers' devices with redundant notifications.*

### User Story 4: Platform Sync Cleared and Subsequent Edits
*As a store manager, after updating Wallapop and Vinted with the new photos, I click "✅ Marcar plataformas como actualizadas". The sync flag resets to `needs_platform_sync = False`. Three days later, I lower the price again; the product transitions `False -> True` and a fresh push notification is dispatched to notify managers of the new change.*

---

## 3. Technical Architecture & Invariants

### 3.1. State Transition Detection Invariant
In `inventory/models.py`:
- Track `_initial_needs_platform_sync = self.needs_platform_sync` on model initialization (`__init__`).
- In `save()`, after computing field changes and setting `needs_platform_sync = True`:
  - Record `self._previous_needs_platform_sync = getattr(self, "_initial_needs_platform_sync", False)`
  - Update `self._initial_needs_platform_sync = self.needs_platform_sync`
- In `post_save` signal receiver (`notify_managers_on_product_lifecycle_save`):
  - Detect edge transition:
    ```python
    was_in_sync = not getattr(instance, "_previous_needs_platform_sync", False)
    if instance.needs_platform_sync and was_in_sync and not instance.is_deleted:
        send_out_of_sync_notification(instance)
    ```

### 3.2. Push Service Dispatcher (`inventory/services/push_service.py`)
Add a dedicated high-level notification helper:
```python
def send_out_of_sync_notification(product, trigger_reason: str | None = None) -> int:
    """
    Send Web Push notification to all active Store Managers when a published product
    transitions to out of sync with external platforms.
    """
    if not getattr(settings, "PUSH_NOTIFICATIONS_LIVE_SIGNALS", False):
        return 0
    from inventory.permissions import ROLE_MANAGER

    title = str(_("⚠️ Product Out of Sync: %(title)s") % {"title": product.display_title})
    body = str(_("Modifications detected on published item. External platform listings require updating."))
    url = f"/products/{product.pk}/"
    tag = f"product-out-of-sync-{product.pk}"

    return send_push_to_group(
        group_name=ROLE_MANAGER,
        title=title,
        body=body,
        url=url,
        tag=tag,
    )
```

### 3.3. Key Invariants
1. **Manager Role Only**: Out-of-sync notifications must only target store managers, staff, and superusers (`ROLE_MANAGER`), not sourcing assistants.
2. **Edge-Triggered Only**: Must fire strictly on `False -> True` transitions of `needs_platform_sync`.
3. **Suppression on Sync Clearance**: `mark_platform_synced()` sets `needs_platform_sync = False`; no out-of-sync notification must be dispatched.
4. **Deleted Products Ignored**: If a product is soft-deleted, it must not trigger out-of-sync notifications.
5. **Robust Error Handling**: Push notification dispatch failures (network timeouts, expired subscriptions) must be silently logged and never fail or roll back the core product save transaction.

---

## 4. Verification & Testing Strategy
1. **Unit & Service Tests (`tests/test_out_of_sync_notifications.py`)**:
   - `send_out_of_sync_notification` dispatches push to `ROLE_MANAGER` with correct title, body, URL, and tag.
   - Respects `PUSH_NOTIFICATIONS_LIVE_SIGNALS = False` (returns 0, no push sent).
   - Only managers receive the notification; assistants do not.
2. **Lifecycle & Signal Transition Tests**:
   - Price change on published product (`False -> True`) dispatches notification.
   - Copywriting edit on published product (`False -> True`) dispatches notification.
   - Adding photo to published product (`False -> True`) dispatches notification.
   - Deleting photo from published product (`False -> True`) dispatches notification.
   - Reordering cover photo on published product (`False -> True`) dispatches notification.
   - Adding clarification to published product (`False -> True`) dispatches notification.
   - Subsequent edit on already out-of-sync product (`True -> True`) does NOT dispatch duplicate notification.
   - Clearing platform sync (`True -> False`) does NOT dispatch notification.
   - Editing after clearing sync (`False -> True`) dispatches a fresh notification.
   - Editing draft or unpublished items does NOT dispatch out-of-sync notification.
3. **Bilingual Localization Tests**:
   - Verify Spanish and English title/body formatting.
4. **Regression & Quality Gates**:
   - 100% test pass rate across entire project suite (455+ tests).
   - Clean linter (`ruff check .`) and Django check (`manage.py check`).
