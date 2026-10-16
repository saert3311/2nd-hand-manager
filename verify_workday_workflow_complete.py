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
    page.wait_for_selector('input[name="username"]')
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)

    # Allow Turnstile to populate client token with Cloudflare testing sitekey
    for _ in range(20):
        val = page.evaluate('() => document.querySelector(\'[name="cf-turnstile-response"]\')?.value || ""')
        if val:
            break
        time.sleep(0.2)

    page.click('form[action*="login"] button[type="submit"]')
    page.wait_for_url(lambda u: "/intake/" in u or "/dashboard/" in u, timeout=15000)
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


def run_workday_browser_verification():
    print("=" * 70)
    print("STARTING COMPLETE NORMAL WORKDAY REAL-BROWSER VERIFICATION")
    print("=" * 70)

    # 1. Setup Django environment and demo roles
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django
    django.setup()
    from django.core.management import call_command
    call_command("setup_roles")

    from inventory.models import Product, ProductClarification

    # Clean existing test artifacts for deterministic baseline
    ProductClarification.objects.all().delete()
    Product.objects.filter(raw_note__contains="Ralph Lauren Denim Jacket").delete()

    sample_images = generate_sample_images()
    print(f"Generated sample images: {sample_images}")

    server_proc, server_log = start_server_if_needed()
    created_product_id = None

    try:
        with sync_playwright() as p:
            print(f"Launching Google Chrome executable at: {CHROME_PATH}")
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

            console_messages = []
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

            network_failures = []
            page.on("requestfailed", lambda req: network_failures.append(f"FAILED: {req.method} {req.url} - {req.failure}") if BASE_URL in req.url else None)
            page.on("response", lambda resp: network_failures.append(f"HTTP {resp.status}: {resp.url}") if resp.status >= 400 and BASE_URL in resp.url and "/admin/" not in resp.url and "favicon" not in resp.url else None)

            # ==============================================================
            # STEP 1: ASSISTANT LOGIN & ROLE GATING
            # ==============================================================
            print("\n--- STEP 1: Assistant Authentication & Access Controls ---")
            login_user(page, context, "assistant", "assistant123")
            print(f"Logged in as assistant, current URL: {page.url}")
            assert "/intake/" in page.url, f"Expected assistant redirected to /intake/, got {page.url}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "01_assistant_login_intake.png"))
            print("Captured screenshot: 01_assistant_login_intake.png")

            # Verify Assistant cannot enter /admin/ (strict 403 Forbidden gating)
            print("Verifying assistant cannot access Django Admin (/admin/)...")
            resp_admin = page.goto(f"{BASE_URL}/admin/")
            page.wait_for_load_state("domcontentloaded")
            print(f"Assistant /admin/ HTTP status: {resp_admin.status}")
            assert resp_admin.status == 403, f"Expected 403 Forbidden, got {resp_admin.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "02_assistant_admin_forbidden.png"))
            print("Captured screenshot: 02_assistant_admin_forbidden.png")

            # ==============================================================
            # STEP 2: INTAKE WITH MULTI-PHOTO UPLOAD, PREVIEW DELETION & PRICE
            # ==============================================================
            print("\n--- STEP 2: Intake Flow (Previews, Photo Deletion, Price Input) ---")
            page.goto(f"{BASE_URL}/intake/")
            page.wait_for_load_state("domcontentloaded")

            # 2.1 Attach 3 photos to file input
            file_input = page.locator('#imageInput')
            file_input.set_input_files(sample_images)
            time.sleep(1)

            preview_cards = page.locator("#previewGrid > div")
            print(f"Preview cards displayed after 3 files attached: {preview_cards.count()}")
            assert preview_cards.count() == 3, f"Expected 3 preview cards, found {preview_cards.count()}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "03_intake_previews_3_photos.png"))
            print("Captured screenshot: 03_intake_previews_3_photos.png")

            # 2.2 Test Single Photo Deletion (Removing 3rd wrong photo without re-uploading)
            print("Testing individual photo delete button on photo #3...")
            delete_buttons = page.locator(".photo-delete-btn")
            assert delete_buttons.count() == 3, f"Expected 3 delete buttons, found {delete_buttons.count()}"
            delete_buttons.nth(2).click()
            time.sleep(1)

            cards_after_delete = page.locator("#previewGrid > div")
            print(f"Preview cards after deleting 3rd photo: {cards_after_delete.count()}")
            assert cards_after_delete.count() == 2, f"Expected 2 preview cards remaining, found {cards_after_delete.count()}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_intake_after_photo_deleted.png"))
            print("Captured screenshot: 04_intake_after_photo_deleted.png")

            # 2.3 Fill Notes and Sale Price (125.50)
            note_text = "Vintage 90s Ralph Lauren Denim Jacket with corduroy collar, size L, excellent condition."
            page.fill('textarea[name="raw_note"]', note_text)
            page.fill('input[name="sale_price"]', "125.50")
            page.screenshot(path=str(SCREENSHOTS_DIR / "05_intake_filled_with_price.png"))
            print("Captured screenshot: 05_intake_filled_with_price.png")

            # 2.4 Submit Intake Form
            print("Submitting intake form...")
            page.click("#submitBtn")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "06_intake_success_recent_upload.png"))
            print("Captured screenshot: 06_intake_success_recent_upload.png")
            assert "catalogado" in page.content() or "Producto #" in page.content() or "Recent" in page.content() or "Recientes" in page.content()

            # Retrieve created product ID and verify sale_price
            new_prod = Product.objects.filter(raw_note__contains="Ralph Lauren Denim Jacket").order_by("-id").first()
            assert new_prod is not None, "Product was not found in DB!"
            created_product_id = new_prod.id
            print(f"Created Product in DB ID: {created_product_id}, price: {new_prod.sale_price}")
            assert float(new_prod.sale_price) == 125.50, f"Expected sale price 125.50, got {new_prod.sale_price}"

            # ==============================================================
            # STEP 3: ASSISTANT DASHBOARD VIEW & PRICE DISPLAY
            # ==============================================================
            print("\n--- STEP 3: Assistant Dashboard View & Price Badge ---")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "07_assistant_dashboard_price_badge.png"))
            print("Captured screenshot: 07_assistant_dashboard_price_badge.png")

            # Check that price is rendered on dashboard card
            dashboard_content = page.content()
            assert "125,50" in dashboard_content or "125.50" in dashboard_content, "Expected price €125.50 on dashboard card"

            # Test text search
            print("Testing text search for 'Ralph Lauren'...")
            page.fill('input[name="q"]', "Ralph Lauren")
            page.press('input[name="q"]', "Enter")
            page.wait_for_load_state("domcontentloaded")
            assert "Ralph Lauren" in page.content()

            # Assistant views detail page (read-only verification)
            print(f"Assistant viewing product detail: /products/{created_product_id}/...")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "08_assistant_readonly_product_detail.png"))
            print("Captured screenshot: 08_assistant_readonly_product_detail.png")
            # Verify assistant sees price badge and cannot edit manager fields
            assert "125,50" in page.content() or "125.50" in page.content()
            assert page.locator('button[type="submit"]:has-text("Guardar Cambios"), button[type="submit"]:has-text("Save Changes"), button[type="submit"]:has-text("Guardar Cambios del Producto")').count() == 0
            print("Verified assistant has strictly read-only view of product detail!")

            # ==============================================================
            # STEP 4: MOBILE VIEWPORT & HAMBURGER SANDWICH MENU
            # ==============================================================
            print("\n--- STEP 4: Mobile Viewport & Hamburger Menu ---")
            page.set_viewport_size({"width": 390, "height": 844})  # iPhone 14
            time.sleep(1)
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "09_mobile_viewport_collapsed_navbar.png"))
            print("Captured screenshot: 09_mobile_viewport_collapsed_navbar.png")

            # Check hamburger button visible, desktop nav hidden
            menu_btn = page.locator("#mobile-menu-button")
            assert menu_btn.is_visible(), "Expected mobile hamburger menu button to be visible"
            assert not page.locator("#desktop-nav").is_visible(), "Expected desktop nav to be hidden on mobile"

            # Open mobile menu
            menu_btn.click()
            time.sleep(0.5)
            mobile_menu = page.locator("#mobile-menu")
            assert mobile_menu.is_visible(), "Expected mobile menu drawer to open"
            page.screenshot(path=str(SCREENSHOTS_DIR / "10_mobile_drawer_open.png"))
            print("Captured screenshot: 10_mobile_drawer_open.png")

            # Toggle language to English in mobile menu
            print("Testing language switch to English in mobile drawer...")
            en_btn = mobile_menu.locator('button[value="en"]').first
            en_btn.click()
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "11_mobile_drawer_switched_to_english.png"))
            print("Captured screenshot: 11_mobile_drawer_switched_to_english.png")
            assert "Dashboard" in page.content() or "New Intake" in page.content()

            # Toggle language back to Spanish
            print("Restoring Spanish language...")
            menu_btn = page.locator("#mobile-menu-button")
            menu_btn.click()
            time.sleep(0.5)
            es_btn = page.locator('#mobile-menu button[value="es"]').first
            es_btn.click()
            page.wait_for_load_state("domcontentloaded")

            # Restore desktop viewport
            page.set_viewport_size({"width": 1366, "height": 900})
            time.sleep(0.5)

            # ==============================================================
            # STEP 5: MANAGER WORKFLOW & STAGING DETAIL PRICING CHECK
            # ==============================================================
            print("\n--- STEP 5: Manager Workflow & Staging Detail Price Input ---")
            login_user(page, context, "manager", "manager123")
            print(f"Logged in as manager, current URL: {page.url}")
            assert "/dashboard/" in page.url

            # Open Staging Page for newly created item
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "12_manager_staging_price_detail.png"))
            print("Captured screenshot: 12_manager_staging_price_detail.png")

            # VERIFY THE HTML5 NUMBER INPUT HAS VALUE "125.50" (Unlocalized fix verification!)
            price_input = page.locator('#id_sale_price')
            assert price_input.count() > 0, "Expected #id_sale_price to exist"
            price_val = price_input.first.input_value()
            print(f"Price input value in Manager Staging: '{price_val}'")
            assert price_val == "125.50", f"Expected price input value '125.50', got '{price_val}'"

            # Price badge check
            badge_loc = page.locator("#product-price-badge")
            if badge_loc.count() > 0:
                badge_text = badge_loc.first.inner_text()
                print(f"Price badge text: '{badge_text}'")
                assert "125,50" in badge_text or "125.50" in badge_text

            # Manager updates title and description
            print("Manager updating product title...")
            page.fill('input[name="ai_title"]', "Cazadora Vaquera Vintage Ralph Lauren Polo")
            page.click('button[type="submit"]:has-text("Guardar Cambios"), button[type="submit"]:has-text("Save Listing Changes")')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "13_manager_staging_saved.png"))
            print("Captured screenshot: 13_manager_staging_saved.png")
            assert "Cazadora Vaquera Vintage Ralph Lauren Polo" in page.content()

            # ==============================================================
            # STEP 6: CLARIFICATION Q&A WORKFLOW & BADGE SYNC
            # ==============================================================
            print("\n--- STEP 6: Clarification Q&A Workflow & Attention Badge Sync ---")
            # Manager posts a question
            print("Manager posting clarification question...")
            page.fill('textarea[name="question"]', "Por favor revisa si los botones son de latón original.")
            page.click('button[type="submit"]:has-text("Enviar Pregunta"), button[type="submit"]:has-text("Send Question")')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            # Verify badge ❓ Dudas (1) appears in navbar
            dudas_badge = page.locator(".badge-pending-clarifications, #badge-pending-clarifications").first
            assert dudas_badge.is_visible(), "Expected Dudas badge to appear in navbar"
            assert "1" in dudas_badge.inner_text(), f"Expected badge count 1, got {dudas_badge.inner_text()}"
            print("Verified '❓ Dudas (1)' attention badge is visible in navbar!")

            # Click Dudas badge to go to filtered dashboard
            dudas_badge.click()
            page.wait_for_url(lambda u: "status=awaiting_info" in u, timeout=5000)
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "14_dashboard_dudas_badge_and_filtered_list.png"))
            print("Captured screenshot: 14_dashboard_dudas_badge_and_filtered_list.png")

            # Verify Ralph Lauren item is shown and count is 1 (no orphan counts)
            cards_awaiting = page.locator(".grid > div, .grid > a").count()
            print(f"Cards shown on awaiting_info filter: {cards_awaiting}")
            assert cards_awaiting == 1, f"Expected exactly 1 card in awaiting_info, found {cards_awaiting}"
            assert "Ralph Lauren" in page.content()

            # Switch to Assistant to answer the question
            print("Logging in as assistant to resolve doubt...")
            login_user(page, context, "assistant", "assistant123")

            # Assistant opens product detail and responds
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            answer_input = page.locator('form[action*="/answer/"] input[name="answer"]').first
            assert answer_input.is_visible(), "Expected answer input for assistant"
            answer_input.fill("Revisado: son botones de latón original con grabado Polo 1994.")
            page.locator('form[action*="/answer/"] button[type="submit"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            # Verify badge is now CLEARED / 0
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")
            dudas_badge_after = page.locator(".badge-pending-clarifications, #badge-pending-clarifications")
            assert dudas_badge_after.count() == 0, "Expected Dudas badge to be cleared after answer"
            page.screenshot(path=str(SCREENSHOTS_DIR / "15_dudas_resolved_badge_cleared.png"))
            print("Captured screenshot: 15_dudas_resolved_badge_cleared.png")
            print("Verified '❓ Dudas' badge is 0 / cleared after assistant's answer!")

            # ==============================================================
            # STEP 7: MARKETPLACE LISTING LINKS MANAGEMENT (MANAGER)
            # ==============================================================
            print("\n--- STEP 7: Marketplace Listing Links Management ---")
            login_user(page, context, "manager", "manager123")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")

            # Add Wallapop link
            print("Adding Wallapop listing URL...")
            wallapop_card = page.locator('div[data-site-slug="wallapop"]')
            wallapop_card.locator('input[name="url"]').fill("https://es.wallapop.com/item/vintage-rl-denim-jacket-12345")
            wallapop_card.locator('form:has(input[name="url"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")
            assert "vintage-rl-denim-jacket-12345" in page.content()

            # Add Vinted link
            print("Adding Vinted listing URL...")
            vinted_card = page.locator('div[data-site-slug="vinted"]')
            vinted_card.locator('input[name="url"]').fill("https://www.vinted.es/items/vintage-rl-denim-jacket-67890")
            vinted_card.locator('form:has(input[name="url"]) button[type="submit"]').click()
            page.wait_for_load_state("domcontentloaded")
            assert "vintage-rl-denim-jacket-67890" in page.content()

            page.screenshot(path=str(SCREENSHOTS_DIR / "16_marketplace_links_saved.png"))
            print("Captured screenshot: 16_marketplace_links_saved.png")

            # Test Copy URL button
            print("Testing one-click copy URL button...")
            copy_btn = page.locator('button[onclick*="copyLinkUrl"]').first
            copy_btn.click()
            time.sleep(0.5)
            assert "Copiado!" in copy_btn.inner_text() or "Copied!" in copy_btn.inner_text()

            # Check dashboard platform filter dropdown
            print("Checking dashboard platform selector for Wallapop & Vinted...")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("domcontentloaded")
            platform_select = page.locator('select[name="platform"]')
            assert "Wallapop" in platform_select.inner_text()
            assert "Vinted" in platform_select.inner_text()

            # Return to product detail and remove Vinted link
            print("Deleting Vinted link via UI...")
            page.goto(f"{BASE_URL}/products/{created_product_id}/")
            page.wait_for_load_state("domcontentloaded")
            page.on("dialog", lambda dialog: dialog.accept())
            vinted_remove_btn = page.locator('div[data-site-slug="vinted"] form:has(input[value="delete"]) button[type="submit"]').first
            vinted_remove_btn.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "17_marketplace_links_updated.png"))
            print("Captured screenshot: 17_marketplace_links_updated.png")

            # ==============================================================
            # STEP 8: SALE COMPLETION & DASHBOARD STATUS FILTER
            # ==============================================================
            print("\n--- STEP 8: Sale Completion & Status Verification ---")
            page.fill('input[name="sale_price"]', "120.00")
            sold_chk = page.locator('#id_is_sold, input[name="is_sold"]')
            if not sold_chk.is_checked():
                sold_chk.check()
            page.locator('form:has(#id_is_sold) button[type="submit"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            assert "Vendido" in page.content() or "Sold" in page.content()
            page.screenshot(path=str(SCREENSHOTS_DIR / "18_product_marked_sold.png"))
            print("Captured screenshot: 18_product_marked_sold.png")

            # Check dashboard under 'Vendidos' filter
            print("Checking dashboard filter 'status=sold'...")
            page.goto(f"{BASE_URL}/dashboard/?status=sold")
            page.wait_for_load_state("domcontentloaded")
            assert "Ralph Lauren" in page.content()
            assert "120,00" in page.content() or "120.00" in page.content()
            print("Verified sold item displays €120.00 under status=sold!")

            # ==============================================================
            # STEP 9: MANAGER ADMIN SITE & GROUPS INSPECTION
            # ==============================================================
            print("\n--- STEP 9: Manager Admin Site, Groups & Backups ---")
            page.goto(f"{BASE_URL}/admin/")
            page.wait_for_load_state("domcontentloaded")
            admin_index_content = page.content()
            assert "2ndHand Staging" in admin_index_content or "Administración" in admin_index_content or "Administration" in admin_index_content

            # Check Users changelist
            print("Inspecting /admin/auth/user/ with role badges...")
            page.goto(f"{BASE_URL}/admin/auth/user/")
            page.wait_for_load_state("domcontentloaded")
            assert "manager" in page.content()
            assert "assistant" in page.content()

            # Check Groups changelist (CustomGroupAdmin)
            print("Inspecting /admin/auth/group/ (CustomGroupAdmin)...")
            page.goto(f"{BASE_URL}/admin/auth/group/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "19_admin_custom_group_admin.png"))
            print("Captured screenshot: 19_admin_custom_group_admin.png")
            group_content = page.content()
            assert "managers" in group_content
            assert "assistants" in group_content
            print("Verified CustomGroupAdmin lists 'assistants' and 'managers' groups with member count!")

            # Check Backups changelist
            print("Inspecting /admin/inventory/databasebackuplog/...")
            page.goto(f"{BASE_URL}/admin/inventory/databasebackuplog/")
            page.wait_for_load_state("domcontentloaded")
            page.screenshot(path=str(SCREENSHOTS_DIR / "20_admin_backups_list.png"))
            print("Captured screenshot: 20_admin_backups_list.png")

            # ==============================================================
            # STEP 10: AUDIT LOGS & CONSOLE CHECK
            # ==============================================================
            print("\n--- STEP 10: Auditing DevTools Console & Network ---")
            print(f"Total console messages captured: {len(console_messages)}")
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
            print("\n" + "=" * 70)
            print("ALL WORKDAY BROWSER VERIFICATION TESTS PASSED SUCCESSFULLY (100%)!")
            print("=" * 70)

    finally:
        # Clean up sample files and DB product
        for path in sample_images:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

        if created_product_id:
            try:
                from inventory.models import Product
                Product.objects.filter(id=created_product_id).delete()
                print(f"Cleaned up test product ID {created_product_id}")
            except Exception as e:
                print(f"Failed to clean up product: {e}")

        try:
            Path("test_quick_login.py").unlink(missing_ok=True)
        except Exception:
            pass

        if server_proc:
            print("Terminating test dev server process...")
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
    run_workday_browser_verification()
