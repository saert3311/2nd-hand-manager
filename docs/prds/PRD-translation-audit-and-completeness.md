# PRD: Comprehensive Project Texts & Bilingual Localization Audit & Fixes

## 1. Problem Statement & Background
The **2ndHand Staging Hub** and **Rápido Pack** public storefront (`rapidopack.es`) are designed to be fully bilingual (Spanish `es` and English `en`).
A systematic audit of all project texts revealed several significant translation gaps and inconsistencies:
1. **Mixed Source `msgid` Languages**: While the core staging hub (`inventory/templates/`, `inventory/models.py`, `catalog.html`, `login.html`) strictly uses English `msgid`s translated into Spanish via `locale/es/LC_MESSAGES/django.po`, the public storefront templates (`home.html`, `how_to_buy.html`, `_how_to_buy_modal.html`, `base_public.html`, `legal_page.html`) were introduced with mixed Spanish and English `msgid`s (e.g. `{% trans "Tu punto de confianza en Alfafar" %}` and `{% trans "Technically audited" %}`).
2. **Missing Translations in English Mode**: Because `storefront/templates/storefront/home.html` and `how_to_buy.html` used Spanish text as `msgid`, when an English speaker visits `/` or `/como-comprar/` (with `Accept-Language: en` or `django_language=en`), Django finds no translation and outputs the Spanish `msgid`, leaving the corporate landing page entirely in Spanish.
3. **Missing Translations in Spanish Mode**: 63 field labels and help texts in `inventory/models.py` (e.g., `StorefrontConfiguration`, `Category`, `public_views_count`, `deleted_at`, `deleted_by`), 18 form/view labels in `inventory/forms.py` and `inventory/views.py`, 4 image service error messages in `inventory/services/image_service.py`, and 19 staging template texts were marked with `_("...")` but were never added to `locale/es/LC_MESSAGES/django.po`. As a result, in Spanish mode, store managers and staff see untranslated English labels in admin forms and dialogs.
4. **Empty Translation Entry in `django.po`**: Entry `'You have %(count)s product clarification awaiting your answer.'` has an empty `msgstr ""` in `django.po`.
5. **No `locale/en/LC_MESSAGES/django.po`**: Although `config/settings.py` declares `LANGUAGES = [('es', _('Spanish')), ('en', _('English'))]`, `locale/en/LC_MESSAGES` contains no compiled catalog.

## 2. Objectives & Scope
- **Harmonize Source `msgid`s to English**: Standardize all translatable strings in templates and Python code to clean, natural English `msgid`s following standard Django gettext conventions.
- **Complete Spanish Localization Catalog (`locale/es/LC_MESSAGES/django.po`)**: Provide accurate, idiomatic Spanish translations for 100% of the project's translatable strings.
- **Create English Localization Catalog (`locale/en/LC_MESSAGES/django.po`)**: Ensure consistent English message catalogs compiled to binary `.mo` format.
- **Wrap Any Unmarked Strings**: Ensure all customer-facing and manager-facing texts are properly wrapped in `{% trans %}` or `_()`.
- **Browser & Automated Verification**: Verify runtime translations using automated Django unit/integration tests and Playwright real-browser assertions in both Spanish and English.
- **Zero Regressions**: 100% passing test suite (`python manage.py test`), clean Ruff linter, and clean Django check.

## 3. User Experience & Verification
- **Spanish Visitor (`es`)**: Visits `/`, `/tienda/`, `/como-comprar/`, `/aviso-legal/`, `/privacidad/`, `/cookies/`, or `/panel/` and sees natural Spanish everywhere.
- **English Visitor (`en`)**: Visits `/`, `/tienda/`, `/como-comprar/`, `/aviso-legal/`, `/privacidad/`, `/cookies/`, or `/panel/` and sees natural English everywhere.
- **Language Switcher**: Toggling between `ES` and `EN` switches all UI headers, hero titles, descriptions, buttons, badges, modals, legal texts, and footers instantly.
