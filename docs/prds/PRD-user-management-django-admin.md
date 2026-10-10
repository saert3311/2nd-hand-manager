# Product Requirements Document (PRD): User Management & Django Admin Role Gating

## 1. Executive Summary
Provide comprehensive user management capabilities directly within the Django Administration panel (`/admin/`) exclusively accessible to store Managers and Administrators. This feature allows managers to add, modify, deactivate, and remove field assistants and managers, view item cataloging metrics per user, and enforce strict access control preventing non-manager users (assistants) from accessing the administration panel.

---

## 2. Problem Statement
Currently:
1. **Unrestricted Admin Login Intent:** While assistants lack staff flags and cannot edit admin models, any non-manager attempting to visit `/admin/` is greeted by the standard Django admin login page rather than an explicit role-based access denial.
2. **No User Management Customization:** The default Django `UserAdmin` displays standard technical fields (`username`, `email`, `is_staff`, `is_superuser`, `groups`) without role clarity. Managers cannot readily distinguish Assistants from Managers, nor can they view store-specific metrics (e.g. how many secondhand items an assistant has cataloged).
3. **Role Synchronization Friction:** Changing a user from Assistant to Manager requires manually adding them to the `managers` group AND manually toggling `is_staff = True`. If a manager forgets to toggle `is_staff`, the user cannot access the admin.

---

## 3. User Personas & Scenarios

### Persona: Store Manager / Admin (User B)
- **Scenario 1 (Hiring a New Assistant):** A new sourcing assistant joins the shop. The manager logs into `/admin/`, clicks "Users" -> "Add User", provides username and temporary password, selects the "Assistant" role, and saves. The user is automatically placed into the `assistants` group with `is_staff=False`.
- **Scenario 2 (Auditing Assistant Productivity):** The manager views the user list in `/admin/` and sees a dedicated column showing the number of items cataloged by each assistant (e.g. "Item Count: 42"), with clickable links to those products.
- **Scenario 3 (Promoting to Manager):** An assistant is promoted. The manager edits the user in admin and changes their role to "Manager". Group membership (`managers`) and `is_staff=True` are automatically synchronized.
- **Scenario 4 (Offboarding an Assistant):** An assistant leaves the shop. The manager selects the user and chooses the "Deactivate selected users" action. The account is disabled (`is_active=False`), preventing login while preserving historical authorship on `Product.created_by`.

### Persona: Field Sourcing Assistant (User A)
- **Scenario 5 (Unauthorized Access Attempt):** An assistant attempts to navigate directly to `/admin/`. The system intercepts the request and strictly denies access (`403 Forbidden` or redirect to app login), enforcing role boundaries.

---

## 4. Scope & Functional Requirements

### 4.1 Strict Admin Access Control
- **Custom Admin Site (`ManagerAdminSite`):**
  - Subclasses `django.contrib.admin.AdminSite`.
  - Overrides `has_permission(self, request)` to require:
    `request.user.is_active and is_manager(request.user)`.
  - Non-managers (including assistants) are strictly barred from the administration panel.
  - Branded admin site headers:
    - Site Header: `2ndHand Staging - Administration` / `2ndHand Staging - Administración`
    - Site Title: `2ndHand Staging Admin`
    - Index Title: `Store Administration & User Management`

### 4.2 Enhanced UserAdmin (`CustomUserAdmin`)
- **List Display:**
  - `username`
  - `email`
  - `role_badge`: Visual badge distinguishing `Superuser`, `Manager`, `Assistant`, or `None`.
  - `cataloged_items_count`: Total items uploaded by the user with link to filtered product list.
  - `is_active`: Status indicator (active vs deactivated).
  - `date_joined` and `last_login`.
- **Filters & Search:**
  - Custom role filter (`RoleListFilter`: Superuser, Manager, Assistant).
  - Filter by `is_active`, `date_joined`.
  - Search by `username`, `first_name`, `last_name`, `email`.
- **Automatic Role & Staff Flag Synchronization:**
  - When saving a user (`save_model`), if the user is in the `managers` group or superuser, ensure `is_staff = True`.
  - If the user is only in the `assistants` group (and not superuser), ensure `is_staff = False`.
- **Admin Actions:**
  - `make_assistant`: Assign selected users to the `assistants` group and set `is_staff=False`.
  - `make_manager`: Assign selected users to the `managers` group and set `is_staff=True`.
  - `deactivate_users`: Safely deactivate (`is_active=False`) selected users preserving product authorship.
  - `activate_users`: Reactivate selected users.

### 4.3 Multi-Language (i18n) Support
- All custom admin text, role badges, action messages, and filter titles translated into Spanish (`es`) and English (`en`):
  - "Manager" -> "Gestor"
  - "Assistant" -> "Asistente"
  - "Cataloged Items" -> "Artículos Catalogados"
  - "Assign Assistant role" -> "Asignar rol de Asistente"
  - "Assign Manager role" -> "Asignar rol de Gestor"
  - "Deactivate selected users" -> "Desactivar usuarios seleccionados"

---

## 5. Non-Functional Requirements
- **Security:** Strict authorization enforcement at the `AdminSite` level. No privilege escalation.
- **Data Integrity:** Foreign key safety on `Product.created_by` (protected against dangling references via `SET_NULL`).
- **Performance:** Optimized user list query using `annotate(cataloged_count=Count('created_products'))` avoiding N+1 queries.

---

## 6. Success Criteria
1. Only users verified as managers (`is_manager(user) == True`) can log in or access `/admin/`.
2. Assistants attempting to access `/admin/` are strictly blocked.
3. Managers can add, modify, deactivate, and delete assistants and managers in `/admin/`.
4. User list displays role badges and item cataloging counts.
5. Bulk actions for role assignment and deactivation execute safely.
6. Full test suite passes including new admin access and user management tests.
7. Spanish translation catalog compiled and verified.
