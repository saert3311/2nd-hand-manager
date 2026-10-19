import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = Path("browser_verification_screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def is_server_ready(url, timeout=1):
    try:
        req = urllib.request.Request(f"{url}/login/", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 302)
    except Exception:
        return False


def start_server_if_needed():
    if is_server_ready(BASE_URL):
        print(f"[Server] Django dev server already running at {BASE_URL}")
        return None, None

    print(f"[Server] Starting Django dev server at {BASE_URL}...")
    server_log = open("server_workday.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [r".venv\Scripts\python.exe", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        stdout=server_log,
        stderr=server_log,
        cwd=os.getcwd(),
    )
    for _ in range(30):
        time.sleep(1)
        if is_server_ready(BASE_URL):
            print("[Server] Django dev server is ready!")
            return proc, server_log
    server_log.close()
    raise RuntimeError("Timed out waiting for Django server to start")


def generate_sample_images():
    img1_path = Path("sample_workday_front.jpg")
    img2_path = Path("sample_workday_tag.jpg")
    img3_path = Path("sample_workday_wrong.jpg")

    Image.new("RGB", (600, 600), color=(30, 60, 90)).save(img1_path, format="JPEG", quality=90)
    Image.new("RGB", (600, 600), color=(180, 140, 60)).save(img2_path, format="JPEG", quality=90)
    Image.new("RGB", (600, 600), color=(200, 40, 40)).save(img3_path, format="JPEG", quality=90)

    return [str(img1_path.resolve()), str(img2_path.resolve()), str(img3_path.resolve())]


def login_user(page, context, username, password):
    context.clear_cookies()
    page.goto(f"{BASE_URL}/login/")
    page.locator("#id_username").fill(username)
    page.locator("#id_password").fill(password)

    # Allow Turnstile to populate client token with Cloudflare testing sitekey
    for _ in range(20):
        val = page.evaluate('() => document.querySelector(\'[name="cf-turnstile-response"]\')?.value || ""')
        if val:
            break
        time.sleep(0.2)

    with page.expect_navigation():
        page.click("#loginSubmitBtn")
    page.wait_for_load_state("domcontentloaded")


def logout_user(page, context):
    logout_btn = page.locator('form[action*="logout"] button')
    if logout_btn.count() > 0 and logout_btn.first.is_visible():
        logout_btn.first.click()
        page.wait_for_url(lambda u: "/login/" in u, timeout=10000)
    else:
        context.clear_cookies()
        page.goto(f"{BASE_URL}/login/")
        page.wait_for_load_state("domcontentloaded")


def run_full_normal_day_verification():
    print("=" * 80)
    print("STARTING REAL-BROWSER WORKFLOW VERIFICATION: ALL CASES & COMBINATIONS")
    print("=" * 80)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django

    django.setup()
    from django.core.management import call_command

    call_command("setup_roles")

    from inventory.models import MarketplaceSite, Product, ProductClarification, ProductStatus

    # Ensure marketplace sites exist
    MarketplaceSite.objects.get_or_create(slug="wallapop", defaults={"name": "Wallapop", "order": 1, "is_active": True})
    MarketplaceSite.objects.get_or_create(slug="vinted", defaults={"name": "Vinted", "order": 2, "is_active": True})

    # Clean existing test products for deterministic baseline
    ProductClarification.objects.all().delete()
    Product.objects.filter(raw_note__contains="Ralph Lauren Denim Jacket").delete()

    sample_images = generate_sample_images()
    server_proc, server_log = start_server_if_needed()
    created_product_id = None

    try:
        with sync_playwright() as p:
            print(f"Launching Google Chrome at: {CHROME_PATH}")
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )

            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="es-ES",
                extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
            )
            page = context.new_page()

            # Mock AI identification endpoint for fast deterministic response
            def handle_identify(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "success": True,
                        "identified_title": "Cazadora Vaquera Vintage Ralph Lauren Polo",
                        "category": "Ropa Vintage",
                        "detected_attributes": ["Denim 100% algodón", "Cuello de pana", "Botones Polo"],
                        "missing_or_recommended_info": ["Comprobar etiqueta de composición interior", "Revisar puños"],
                        "suggested_note": "Cazadora vaquera Ralph Lauren vintage con cuello de pana marrón, botones metálicos originales.",
                    }),
                )

            page.route("**/intake/identify/", handle_identify)

            console_messages = []
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

            network_failures = []
            page.on("requestfailed", lambda req: network_failures.append(f"FAILED: {req.method} {req.url} - {req.failure}") if BASE_URL in req.url else None)
            page.on("response", lambda resp: network_failures.append(f"HTTP {resp.status}: {resp.url}") if resp.status >= 400 and BASE_URL in resp.url and "/admin/" not in resp.url and "favicon" not in resp.url else None)

            # ==============================================================
            # STEP 1: PWA MANIFEST & ROOT SERVICE WORKER VERIFICATION
            # ==============================================================
            print("\n--- STEP 1: PWA Manifest & Root Service Worker Inspection ---")
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("domcontentloaded")

            manifest_link = page.get_attribute('link[rel="manifest"]', "href")
            print(f"PWA manifest link in DOM: {manifest_link}")
            assert manifest_link == "/manifest.json", f"Expected /manifest.json, got {manifest_link}"

            manifest_resp = page.goto(f"{BASE_URL}/manifest.json")
            assert manifest_resp.status == 200
            manifest_json = manifest_resp.json()
            assert manifest_json["display"] == "standalone"
            assert manifest_json["scope"] == "/"
            assert manifest_json["theme_color"] == "#059669"
            print(f"Verified PWA manifest: '{manifest_json['name']}' (standalone, scope=/).")

            # Check Service Worker file
            sw_resp = page.goto(f"{BASE_URL}/sw.js")
            assert sw_resp.status == 200
            assert sw_resp.headers.get("service-worker-allowed") == "/"
            print("Verified /sw.js is served with Service-Worker-Allowed: /.")

            page.screenshot(path=str(SCREENSHOTS_DIR / "01_pwa_manifest_sw_verified.png"))

            # ==============================================================
            # STEP 2: ASSISTANT LOGIN & ROLE GATING
            # ==============================================================
            print("\n--- STEP 2: Assistant Authentication & Role Gating ---")
            login_user(page, context, "assistant", "assistant123")
            print(f"Logged in as assistant. Redirected URL: {page.url}")
            assert "/intake/" in page.url, f"Expected redirect to /intake/, got {page.url}"

            # Check Desktop Push Toggle Button is rendered in navbar
            push_btn = page.locator("#push-toggle-btn")
            assert push_btn.is_visible(), "Expected push notification toggle button in navbar"
            print("Verified push alert toggle button is visible in top navigation.")

            # Verify Assistant cannot enter /admin/ (strict 403 Forbidden gating)
            admin_resp = page.goto(f"{BASE_URL}/admin/")
            print(f"Assistant access to /admin/ status: {admin_resp.status}")
            assert admin_resp.status == 403, f"Expected 403 Forbidden, got {admin_resp.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "02_assistant_admin_forbidden.png"))

            # ==============================================================
            # STEP 3: INTAKE CLIENT VALIDATIONS & AI PREFLIGHT (CASE 1: DRAFT)
            # ==============================================================
            print("\n--- STEP 3: Intake Form Validation, AI Preflight & DRAFT Creation ---")
            page.goto(f"{BASE_URL}/intake/")
            page.wait_for_load_state("domcontentloaded")

            # 3.1 Submit with 0 photos -> Accessible inline alert banner without alert()
            print("Testing client validation on 0 photos submit...")
            page.click("#submitBtn")
            time.sleep(0.5)
            alert_box = page.locator("#intakeClientAlert")
            assert alert_box.is_visible(), "Expected #intakeClientAlert to be visible on 0 photos submit"
            print(f"Validation banner text: '{alert_box.inner_text()}'")
            page.screenshot(path=str(SCREENSHOTS_DIR / "03_intake_0_photos_alert.png"))

            # 3.2 Attach 3 sample photos
            print("Attaching 3 sample photos...")
            page.set_input_files("#imageInput", sample_images)
            time.sleep(1)
            preview_cards = page.locator("#previewGrid > div")
            assert preview_cards.count() == 3, f"Expected 3 preview cards, got {preview_cards.count()}"

            # 3.3 Test On-Demand AI Identification
            print("Clicking 'Identificar producto' button...")
            page.click("#identifyBtn")
            page.wait_for_selector("#aiAdvisoryBanner:not(.hidden)", timeout=10000)
            hidden_ai_title = page.input_value("#id_ai_title")
            print(f"Auto-populated hidden ai_title: '{hidden_ai_title}'")
            assert hidden_ai_title == "Cazadora Vaquera Vintage Ralph Lauren Polo"
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_intake_ai_preflight_identified.png"))

            # 3.4 Delete wrong photo #3
            print("Deleting photo #3 using individual delete button...")
            page.locator(".photo-delete-btn").nth(2).click()
            time.sleep(0.5)
            assert page.locator("#previewGrid > div").count() == 2

            # 3.5 Fill raw note, leave description empty, leave price empty -> CREATE DRAFT
            note_text = "Vintage 90s Ralph Lauren Denim Jacket with corduroy collar, size L."
            page.fill('textarea[name="raw_note"]', note_text)
            page.screenshot(path=str(SCREENSHOTS_DIR / "05_intake_ready_to_save_draft.png"))

            print("Submitting intake form (Case 1: No description, no price -> DRAFT)...")
            page.click("#submitBtn")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod = Product.objects.filter(raw_note__contains="Ralph Lauren Denim Jacket").order_by("-id").first()
            assert created_prod is not None, "Product was not found in DB!"
            created_product_id = created_prod.id
            print(f"Created Product ID: {created_product_id}, Status: '{created_prod.status}', Sale Price: {created_prod.sale_price}")
            assert created_prod.status == ProductStatus.DRAFT, f"Expected DRAFT status, got {created_prod.status}"
            assert created_prod.ai_title == "Cazadora Vaquera Vintage Ralph Lauren Polo", "Expected hidden ai_title to persist"
            page.screenshot(path=str(SCREENSHOTS_DIR / "06_intake_created_draft.png"))

            # ==============================================================
            # STEP 4: MOBILE VIEWPORT & HAMBURGER DRAWER
            # ==============================================================
            print("\n--- STEP 4: Mobile Viewport & Hamburger Drawer Navigation ---")
            page.set_viewport_size({"width": 390, "height": 844})  # iPhone 14
            time.sleep(0.5)
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")

            menu_button = page.locator("#mobile-menu-button")
            assert menu_button.is_visible(), "Expected mobile menu button to be visible"
            assert not page.locator("#desktop-nav").is_visible(), "Expected desktop nav to be hidden"

            # Open drawer
            menu_button.click()
            time.sleep(0.5)
            mobile_menu = page.locator("#mobile-menu")
            assert mobile_menu.is_visible(), "Expected mobile drawer to open"

            # Check push toggle button in mobile menu
            mobile_push_btn = page.locator("#mobile-push-toggle-btn")
            assert mobile_push_btn.is_visible(), "Expected push toggle button in mobile drawer"
            print("Verified push alert toggle in mobile navigation drawer.")
            page.screenshot(path=str(SCREENSHOTS_DIR / "07_mobile_drawer_push_toggle.png"))

            # Restore desktop viewport
            page.set_viewport_size({"width": 1366, "height": 900})
            time.sleep(0.5)

            # ==============================================================
            # STEP 5: MANAGER STAGING & TRANSITION TO PRICE_PENDING (CASE 2)
            # ==============================================================
            print("\n--- STEP 5: Manager Staging & Auto-Transition to PRICE_PENDING ---")
            login_user(page, context, "manager", "manager123")
            print(f"Logged in as manager. Current URL: {page.url}")
            assert "/dashboard/" in page.url

            # Open product detail
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "08_manager_staging_draft_detail.png"))

            # Add AI description while keeping price empty -> Transitions to PRICE_PENDING
            print("Adding description with no price to trigger PRICE_PENDING...")
            page.fill(
                'textarea[name="ai_description"]',
                "Cazadora vaquera clásica Ralph Lauren Polo de los años 90 con cuello de pana y corte vintage holgado.",
            )
            page.click('button[type="submit"]:has-text("Guardar Cambios"), button[type="submit"]:has-text("Save Listing Changes")')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product ID {created_product_id} Status after description: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.PRICE_PENDING, f"Expected PRICE_PENDING, got {created_prod.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "09_manager_staging_price_pending.png"))

            # ==============================================================
            # STEP 6: DASHBOARD FILTER TAB "PRECIO PENDIENTE" (CASE 3)
            # ==============================================================
            print("\n--- STEP 6: Dashboard 'Precio pendiente' Filter Tab ---")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")

            # Click "Precio pendiente" tab
            price_pending_tab = page.locator('a[href*="status=price_pending"]')
            assert price_pending_tab.is_visible(), "Expected 'Precio pendiente' tab on dashboard"
            print(f"Tab text: '{price_pending_tab.inner_text()}'")
            price_pending_tab.click()
            page.wait_for_url(lambda u: "status=price_pending" in u, timeout=5000)
            page.wait_for_load_state("domcontentloaded")

            # Verify product is listed under price_pending filter
            assert "Ralph Lauren" in page.content()
            page.screenshot(path=str(SCREENSHOTS_DIR / "10_dashboard_price_pending_filter.png"))
            print("Verified product is accurately listed under 'Precio pendiente' filter tab!")

            # ==============================================================
            # STEP 7: MANAGER SETS SALE PRICE -> READY TO PUBLISH (CASE 4)
            # ==============================================================
            print("\n--- STEP 7: Manager Inputs Price -> Auto-Transition to READY ---")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")

            # Fill price 125.50
            print("Entering sale price 125.50...")
            page.fill('input[name="sale_price"]', "125.50")
            page.click('button[type="submit"]:has-text("Guardar Cambios"), button[type="submit"]:has-text("Save Listing Changes")')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product ID {created_product_id} Status after price: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.READY, f"Expected READY, got {created_prod.status}"
            assert float(created_prod.sale_price) == 125.50

            # Verify header price badge displays €125.50
            badge_loc = page.locator("#product-price-badge")
            if badge_loc.count() > 0:
                print(f"Header price badge: '{badge_loc.inner_text()}'")
                assert "125,50" in badge_loc.inner_text() or "125.50" in badge_loc.inner_text()
            page.screenshot(path=str(SCREENSHOTS_DIR / "11_manager_product_ready_with_price.png"))

            # ==============================================================
            # STEP 8: CLARIFICATION Q&A WORKFLOW (CASE 5: AWAITING_INFO)
            # ==============================================================
            print("\n--- STEP 8: Clarification Doubts Q&A & Attention Badge Sync ---")
            # Manager posts a question
            print("Manager submitting question to assistant...")
            page.fill('textarea[name="question"]', "¿Los botones son de latón macizo con el logo Polo grabado?")
            page.click('button[type="submit"]:has-text("Enviar Pregunta"), button[type="submit"]:has-text("Send Question")')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product Status after question: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.AWAITING_INFO, f"Expected AWAITING_INFO, got {created_prod.status}"

            # Verify badge ❓ Dudas (1) appears in navbar
            dudas_badge = page.locator(".badge-pending-clarifications, #badge-pending-clarifications").first
            assert dudas_badge.is_visible(), "Expected Dudas badge to appear in navbar"
            assert "1" in dudas_badge.inner_text()
            print("Verified '❓ Dudas (1)' attention badge is visible in navbar!")
            page.screenshot(path=str(SCREENSHOTS_DIR / "12_dudas_badge_active.png"))

            # Assistant logs in on mobile viewport to answer
            print("Switching to assistant on mobile to answer doubt...")
            page.set_viewport_size({"width": 390, "height": 844})
            login_user(page, context, "assistant", "assistant123")

            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            answer_input = page.locator('form[action*="/answer/"] input[name="answer"]').first
            assert answer_input.is_visible()
            answer_input.fill("Comprobado: botones de latón macizo originales con sello Polo 1994.")
            page.locator('form[action*="/answer/"] button[type="submit"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product Status after answer: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.READY, f"Expected auto-transition back to READY, got {created_prod.status}"

            # Verify badge is now CLEARED / 0
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")
            assert page.locator(".badge-pending-clarifications, #badge-pending-clarifications").count() == 0
            print("Verified '❓ Dudas' badge cleared after answer!")
            page.screenshot(path=str(SCREENSHOTS_DIR / "13_dudas_answered_badge_cleared.png"))

            # Restore desktop viewport
            page.set_viewport_size({"width": 1366, "height": 900})

            # ==============================================================
            # STEP 9: MARKETPLACE LINKS & PUBLISHING (CASE 6: PUBLISHED)
            # ==============================================================
            print("\n--- STEP 9: Marketplace Listing Links -> Auto-Transition to PUBLISHED ---")
            login_user(page, context, "manager", "manager123")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")

            # Add Wallapop link
            print("Adding Wallapop listing URL...")
            wallapop_card = page.locator('div[data-site-slug="wallapop"]')
            wallapop_card.locator('input[name="url"]').fill("https://es.wallapop.com/item/vintage-rl-denim-jacket-999")
            wallapop_card.locator('form:has(input[name="url"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product Status after adding marketplace link: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.PUBLISHED, f"Expected PUBLISHED, got {created_prod.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "14_product_published_with_link.png"))

            # Add Vinted link
            print("Adding Vinted listing URL...")
            vinted_card = page.locator('div[data-site-slug="vinted"]')
            vinted_card.locator('input[name="url"]').fill("https://www.vinted.es/items/vintage-rl-denim-jacket-888")
            vinted_card.locator('form:has(input[name="url"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")

            # Test Copy URL button
            print("Testing one-click copy URL button...")
            copy_btn = page.locator('button[onclick*="copyLinkUrl"]').first
            copy_btn.click()
            time.sleep(0.5)
            assert "Copiado!" in copy_btn.inner_text() or "Copied!" in copy_btn.inner_text()

            # Test Dashboard Platform Filter
            page.goto(f"{BASE_URL}/dashboard/?platform=wallapop")
            page.wait_for_load_state("domcontentloaded")
            assert "Ralph Lauren" in page.content()

            # Return to product and delete both links -> Reverts to READY
            print("Deleting links to verify auto-reversion to READY...")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            page.on("dialog", lambda d: d.accept())

            # Delete Wallapop
            page.locator('div[data-site-slug="wallapop"] form:has(input[value="delete"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(0.5)

            # Delete Vinted
            page.locator('div[data-site-slug="vinted"] form:has(input[value="delete"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product Status after deleting all links: '{created_prod.status}'")
            assert created_prod.status == ProductStatus.READY, f"Expected auto-reversion to READY, got {created_prod.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "15_product_reverted_to_ready.png"))

            # ==============================================================
            # STEP 10: SALE COMPLETION (CASE 7: SOLD)
            # ==============================================================
            print("\n--- STEP 10: Mark as Sold -> Status SOLD & Unsold Reversion ---")
            page.fill('input[name="sale_price"]', "120.00")
            sold_chk = page.locator('#id_is_sold, input[name="is_sold"]')
            if not sold_chk.is_checked():
                sold_chk.check()
            page.locator('form:has(#id_is_sold) button[type="submit"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            created_prod.refresh_from_db()
            print(f"Product Status marked sold: '{created_prod.status}', is_sold: {created_prod.is_sold}")
            assert created_prod.status == ProductStatus.SOLD
            assert created_prod.is_sold is True
            page.screenshot(path=str(SCREENSHOTS_DIR / "16_product_marked_sold.png"))

            # Check dashboard under 'Vendidos' filter
            page.goto(f"{BASE_URL}/dashboard/?status=sold")
            page.wait_for_load_state("domcontentloaded")
            assert "Ralph Lauren" in page.content()
            assert "120,00" in page.content() or "120.00" in page.content()

            # ==============================================================
            # STEP 11: MANAGER ADMIN PANEL & AUDIT
            # ==============================================================
            print("\n--- STEP 11: Manager Administration Panel & Groups ---")
            page.goto(f"{BASE_URL}/admin/")
            page.wait_for_load_state("domcontentloaded")
            assert "2ndHand Staging" in page.content() or "Administración" in page.content()

            # Check Groups changelist (CustomGroupAdmin)
            page.goto(f"{BASE_URL}/admin/auth/group/")
            page.wait_for_load_state("domcontentloaded")
            assert "managers" in page.content()
            assert "assistants" in page.content()

            # Check Push Subscriptions changelist
            page.goto(f"{BASE_URL}/admin/inventory/pushsubscription/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "17_admin_push_subscriptions.png"))

            # Check Database Backup changelist
            page.goto(f"{BASE_URL}/admin/inventory/databasebackuplog/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "18_admin_backups_list.png"))

            # ==============================================================
            # STEP 12: DEVTOOLS CONSOLE & NETWORK INTEGRITY
            # ==============================================================
            print("\n--- STEP 12: DevTools Console & Network Audit ---")
            print(f"Total console messages logged: {len(console_messages)}")
            critical_errors = [
                c for c in console_messages
                if "error" in c.lower()
                and "favicon" not in c.lower()
                and "404" not in c.lower()
                and "403" not in c.lower()
            ]
            print(f"Critical console errors: {critical_errors}")
            assert len(critical_errors) == 0, f"Found console errors: {critical_errors}"

            print(f"Network failures: {network_failures}")
            assert len(network_failures) == 0, f"Found network failures: {network_failures}"

            browser.close()
            print("\n" + "=" * 80)
            print("ALL WORKFLOW CASES & COMBINATIONS VERIFIED SUCCESSFULLY IN GOOGLE CHROME!")
            print("=" * 80)

    finally:
        for path in sample_images:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

        if created_product_id:
            try:
                Product.objects.filter(id=created_product_id).delete()
                print(f"Cleaned up test product ID {created_product_id}")
            except Exception:
                pass

        if server_proc:
            print("Stopping test dev server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except Exception:
                server_proc.kill()
        if server_log:
            try:
                server_log.close()
            except Exception:
                pass


if __name__ == "__main__":
    run_full_normal_day_verification()
