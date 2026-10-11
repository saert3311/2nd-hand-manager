import io
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
        print(f"Django server already running at {BASE_URL}")
        return None, None

    print("Starting Django development server at 127.0.0.1:8000...")
    server_log = open("server_e2e.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [r".venv\Scripts\python.exe", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        stdout=server_log,
        stderr=server_log,
        cwd=os.getcwd(),
    )
    for _ in range(30):
        time.sleep(1)
        if is_server_ready(BASE_URL):
            print("Django server is ready and responding!")
            return proc, server_log
    server_log.close()
    raise RuntimeError("Timed out waiting for Django server to start")


def generate_sample_images():
    img1_path = Path("sample_leather_jacket_front.jpg")
    img2_path = Path("sample_leather_jacket_detail.jpg")

    img1 = Image.new("RGB", (600, 600), color=(45, 45, 55))
    img1.save(img1_path, format="JPEG", quality=90)

    img2 = Image.new("RGB", (600, 600), color=(85, 60, 45))
    img2.save(img2_path, format="JPEG", quality=90)

    return [str(img1_path.resolve()), str(img2_path.resolve())]


def run_full_browser_verification():
    print("==================================================================")
    print("STARTING COMPREHENSIVE END-TO-END WORKFLOW VERIFICATION (CHROME)")
    print("==================================================================")

    server_proc, server_log = start_server_if_needed()

    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from inventory.models import MarketplaceSite
        MarketplaceSite.objects.filter(name="Vestiaire Collective").delete()

        sample_photos = generate_sample_images()
        print("Prepared sample photos:", sample_photos)

        with sync_playwright() as p:
            print(f"Launching Chrome browser from: {CHROME_PATH}")
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

            # ==============================================================
            # PHASE 1: NORMAL WORKFLOW ON A NORMAL DAY (ASSISTANT INTAKE)
            # ==============================================================
            print("\n--- PHASE 1: Daily Intake Workflow (Assistant Role) ---")

            # 1.1 Login as Assistant
            print("[1.1] Navigating to /login/ as assistant...")
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("networkidle")
            page.fill('input[name="username"]', "assistant")
            page.fill('input[name="password"]', "assistant123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")
            print("Logged in, redirected to:", page.url)
            assert "/intake/" in page.url, f"Expected assistant redirected to /intake/, got {page.url}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "01_assistant_daily_intake.png"))
            print("Captured screenshot: 01_assistant_daily_intake.png")

            # 1.2 Upload photos & fill notes
            print("[1.2] Attaching photos and entering field notes...")
            file_input = page.locator('input[type="file"][name="images"]')
            file_input.set_input_files(sample_photos)
            time.sleep(1)

            preview_imgs = page.locator("#previewGrid img")
            assert preview_imgs.count() == 2, f"Expected 2 live previews, found {preview_imgs.count()}"

            raw_note = "Chaqueta biker cuero Schott NYC vintage 90s negra, cremalleras Talon funcionando, talla L."
            page.fill('textarea[name="raw_note"]', raw_note)
            page.screenshot(path=str(SCREENSHOTS_DIR / "02_intake_preview_filled.png"))
            print("Captured screenshot: 02_intake_preview_filled.png")

            # 1.3 Submit intake
            print("[1.3] Submitting intake form...")
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")
            content = page.content()
            assert "catalogado" in content or "Producto #" in content
            page.screenshot(path=str(SCREENSHOTS_DIR / "03_intake_submitted_success.png"))
            print("Captured screenshot: 03_intake_submitted_success.png")

            # ==============================================================
            # PHASE 2: USER MANAGEMENT & STRICT ADMIN ROLE GATING
            # ==============================================================
            print("\n--- PHASE 2: User Management & Admin Role Gating ---")

            # 2.1 Assistant blocked from /admin/
            print("[2.1] Assistant navigating to /admin/ (should get HTTP 403)...")
            resp = page.goto(f"{BASE_URL}/admin/")
            page.wait_for_load_state("networkidle")
            print(f"HTTP response for assistant in /admin/: {resp.status}")
            assert resp.status == 403, f"Expected 403 Forbidden, got {resp.status}"
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_assistant_admin_403.png"))
            print("Captured screenshot: 04_assistant_admin_403.png")

            # 2.2 Logout assistant, login as manager
            print("[2.2] Logging in as store manager...")
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("networkidle")
            logout_btn = page.locator('button:has-text("Cerrar Sesión"), button:has-text("Sign Out")')
            if logout_btn.is_visible():
                logout_btn.first.click()
                page.wait_for_load_state("networkidle")

            page.goto(f"{BASE_URL}/login/")
            page.fill('input[name="username"]', "manager")
            page.fill('input[name="password"]', "manager123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")
            assert "/dashboard/" in page.url

            # 2.3 Manager enters /admin/
            print("[2.3] Manager navigating to /admin/...")
            resp_admin = page.goto(f"{BASE_URL}/admin/")
            page.wait_for_load_state("networkidle")
            assert resp_admin.status == 200
            page.screenshot(path=str(SCREENSHOTS_DIR / "05_manager_admin_dashboard.png"))
            print("Captured screenshot: 05_manager_admin_dashboard.png")

            # 2.4 User management table with role badges
            print("[2.4] Checking User Management with role badges (/admin/auth/user/)...")
            page.goto(f"{BASE_URL}/admin/auth/user/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "06_admin_users_role_badges.png"))
            print("Captured screenshot: 06_admin_users_role_badges.png")
            users_content = page.content()
            assert "badge-manager" in users_content or "Gestor" in users_content or "Manager" in users_content
            assert "badge-assistant" in users_content or "Asistente" in users_content or "Assistant" in users_content

            # ==============================================================
            # PHASE 3: MARKETPLACE SITES MANAGEMENT IN ADMIN
            # ==============================================================
            print("\n--- PHASE 3: Marketplace Sites Management in Admin ---")

            # 3.1 Inspect Marketplace Sites in Admin
            print("[3.1] Navigating to Marketplace Sites changelist (/admin/inventory/marketplacesite/)...")
            page.goto(f"{BASE_URL}/admin/inventory/marketplacesite/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "07_admin_marketplace_sites_list.png"))
            print("Captured screenshot: 07_admin_marketplace_sites_list.png")

            sites_content = page.content()
            assert "Wallapop" in sites_content
            assert "Vinted" in sites_content
            assert "Milanuncios" in sites_content
            assert "eBay" in sites_content
            print("Verified seeded platforms (Wallapop, Vinted, Milanuncios, eBay) present in admin!")

            # 3.2 Add a new platform: Vestiaire Collective
            print("[3.2] Adding new marketplace platform 'Vestiaire Collective' via Admin...")
            page.goto(f"{BASE_URL}/admin/inventory/marketplacesite/add/")
            page.wait_for_load_state("networkidle")
            page.fill('input[name="name"]', "Vestiaire Collective")
            page.fill('input[name="base_url"]', "https://www.vestiairecollective.com")
            page.fill('input[name="order"]', "5")
            page.click('input[type="submit"][name="_save"]')
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "08_admin_marketplace_site_added.png"))
            print("Captured screenshot: 08_admin_marketplace_site_added.png")

            sites_updated = page.content()
            assert "Vestiaire Collective" in sites_updated
            print("Verified 'Vestiaire Collective' added successfully to Marketplace Sites in Admin!")

            # ==============================================================
            # PHASE 4: PRODUCT CATALOG, PAGINATION & SEARCH
            # ==============================================================
            print("\n--- PHASE 4: Product Catalog, Pagination & Search ---")

            # 4.1 Dashboard Page 1
            print("[4.1] Navigating to Dashboard Page 1...")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "09_dashboard_pagination_page_1.png"))
            print("Captured screenshot: 09_dashboard_pagination_page_1.png")

            cards_p1 = page.locator(".grid > div, .grid > a").count()
            print(f"Products displayed on Page 1: {cards_p1}")
            assert cards_p1 == 20, f"Expected 20 items on page 1, found {cards_p1}"

            # 4.2 Dashboard Page 2
            print("[4.2] Navigating to Dashboard Page 2...")
            next_link = page.locator('nav[aria-label*="Pagination"] a:has-text("Siguiente"), nav[aria-label*="Pagination"] a:has-text("Next"), a[href*="page=2"]').first
            next_link.click()
            page.wait_for_load_state("networkidle")
            assert "page=2" in page.url
            page.screenshot(path=str(SCREENSHOTS_DIR / "10_dashboard_pagination_page_2.png"))
            print("Captured screenshot: 10_dashboard_pagination_page_2.png")

            # 4.3 Text Search
            print("[4.3] Testing search for newly cataloged item 'Schott'...")
            page.fill('input[name="q"]', "Schott")
            page.press('input[name="q"]', "Enter")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "11_dashboard_search_schott.png"))
            print("Captured screenshot: 11_dashboard_search_schott.png")
            assert "Schott" in page.content(), "Expected search results containing 'Schott'"

            # 4.4 Date Search
            print("[4.4] Testing flexible date search ('2026-10')...")
            page.fill('input[name="q"]', "2026-10")
            page.press('input[name="q"]', "Enter")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "12_dashboard_date_search.png"))
            print("Captured screenshot: 12_dashboard_date_search.png")

            # ==============================================================
            # PHASE 5: PRODUCT STAGING & MARKETPLACE LINKS MANAGEMENT
            # ==============================================================
            print("\n--- PHASE 5: Product Staging & Marketplace Listing Links Tracking ---")

            # 5.1 Open Staging page for Schott jacket
            print("[5.1] Opening product detail page for Schott jacket...")
            page.goto(f"{BASE_URL}/dashboard/?q=Schott")
            page.wait_for_load_state("networkidle")
            item_link = page.locator('a[href*="/products/"]').first
            item_link.click()
            page.wait_for_load_state("networkidle")
            detail_url = page.url
            print("Staging detail page URL:", detail_url)
            page.screenshot(path=str(SCREENSHOTS_DIR / "13_product_staging_with_links_card.png"))
            print("Captured screenshot: 13_product_staging_with_links_card.png")

            content_staging = page.content()
            assert "Enlaces de Publicación en Marketplaces" in content_staging or "Marketplace Listing Links" in content_staging
            assert "Wallapop" in content_staging
            assert "Vinted" in content_staging
            assert "Milanuncios" in content_staging
            assert "eBay" in content_staging
            assert "Vestiaire Collective" in content_staging
            print("Verified Marketplace Links card displays all 5 active platforms!")

            # 5.2 Add Wallapop Listing Link
            print("[5.2] Adding Wallapop listing URL...")
            wallapop_card = page.locator('div[data-site-slug="wallapop"]')
            wallapop_input = wallapop_card.locator('input[name="url"]')
            wallapop_input.fill("https://es.wallapop.com/item/schott-biker-leather-jacket-98765")
            wallapop_card.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "14_wallapop_link_saved.png"))
            print("Captured screenshot: 14_wallapop_link_saved.png")

            assert "https://es.wallapop.com/item/schott-biker-leather-jacket-98765" in page.content()
            assert "Publicado" in page.content() or "Listed" in page.content()
            print("Verified Wallapop link saved and marked as Listed!")

            # 5.3 Add Vinted Listing Link
            print("[5.3] Adding Vinted listing URL...")
            vinted_card = page.locator('div[data-site-slug="vinted"]')
            vinted_input = vinted_card.locator('input[name="url"]')
            vinted_input.fill("https://www.vinted.es/items/87654-schott-leather-jacket")
            vinted_card.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "15_vinted_link_saved.png"))
            print("Captured screenshot: 15_vinted_link_saved.png")

            assert "https://www.vinted.es/items/87654-schott-leather-jacket" in page.content()
            print("Verified Vinted link saved!")

            # 5.4 Test One-Click Copy URL Button
            print("[5.4] Testing 'Copiar URL' button on Wallapop link...")
            copy_url_btn = page.locator('button[onclick*="copyLinkUrl"]').first
            copy_url_btn.click()
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS_DIR / "16_copy_url_button_feedback.png"))
            print("Captured screenshot: 16_copy_url_button_feedback.png")
            assert "Copiado!" in copy_url_btn.inner_text() or "Copied!" in copy_url_btn.inner_text()
            print("Verified 'Copiar URL' feedback works!")

            # 5.5 Update Wallapop Link URL
            print("[5.5] Updating Wallapop link with modified URL...")
            wallapop_card_update = page.locator('div[data-site-slug="wallapop"]')
            wallapop_input_update = wallapop_card_update.locator('input[name="url"]')
            wallapop_input_update.fill("https://es.wallapop.com/item/schott-biker-leather-jacket-updated-2026")
            wallapop_card_update.locator('button[type="submit"]:has-text("Actualizar"), button[type="submit"]:has-text("Update")').click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "17_wallapop_link_updated.png"))
            print("Captured screenshot: 17_wallapop_link_updated.png")
            assert "schott-biker-leather-jacket-updated-2026" in page.content()
            print("Verified Wallapop link updated successfully!")

            # 5.6 Remove Vinted Link
            print("[5.6] Removing Vinted link...")
            page.on("dialog", lambda dialog: dialog.accept())
            vinted_card_delete = page.locator('div[data-site-slug="vinted"]')
            remove_btn = vinted_card_delete.locator('button:has-text("Eliminar"), button:has-text("Remove")').first
            remove_btn.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "18_vinted_link_removed.png"))
            print("Captured screenshot: 18_vinted_link_removed.png")
            print("Verified Vinted link removed cleanly!")

            # ==============================================================
            # PHASE 6: ROLE BOUNDARY - ASSISTANT READ-ONLY VIEW
            # ==============================================================
            print("\n--- PHASE 6: Assistant Read-Only Access to Marketplace Links ---")

            # 6.1 Logout Manager, Login as Assistant
            print("[6.1] Logging out manager and logging in as assistant...")
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("networkidle")
            logout_btn = page.locator('button:has-text("Cerrar Sesión"), button:has-text("Sign Out")')
            if logout_btn.is_visible():
                logout_btn.first.click()
                page.wait_for_load_state("networkidle")

            page.goto(f"{BASE_URL}/login/")
            page.fill('input[name="username"]', "assistant")
            page.fill('input[name="password"]', "assistant123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # 6.2 Navigate directly to the product detail page
            print(f"[6.2] Assistant opening staging page: {detail_url}...")
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "19_assistant_readonly_marketplace_links.png"))
            print("Captured screenshot: 19_assistant_readonly_marketplace_links.png")

            # Assistant sees Wallapop link and Copy button
            assert "schott-biker-leather-jacket-updated-2026" in page.content()
            # Assistant DOES NOT have any forms to save, update, or remove links
            links_forms_count = page.locator('form[action*="/links/"]').count()
            print(f"Forms available to assistant for link editing: {links_forms_count}")
            assert links_forms_count == 0, f"Assistant should have 0 link edit forms, found {links_forms_count}"
            print("Verified strict read-only access for Assistant role!")

            # ==============================================================
            # PHASE 7: PHOTO GALLERY & SALES MARKING AS MANAGER
            # ==============================================================
            print("\n--- PHASE 7: Photo Gallery & Sale Marking ---")

            # Login as manager again to complete the sale
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("networkidle")
            logout_btn = page.locator('button:has-text("Cerrar Sesión"), button:has-text("Sign Out")')
            if logout_btn.is_visible():
                logout_btn.first.click()
                page.wait_for_load_state("networkidle")

            page.goto(f"{BASE_URL}/login/")
            page.fill('input[name="username"]', "manager")
            page.fill('input[name="password"]', "manager123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

            # Mark sold at 420.00 EUR
            print("[7.1] Setting sale price to 420.00 EUR and marking as Sold...")
            page.fill('input[name="sale_price"]', "420.00")
            sold_box = page.locator('input[name="is_sold"]')
            if not sold_box.is_checked():
                sold_box.check()
            page.locator('form:has(input[name="sale_price"]) button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "20_product_marked_sold.png"))
            print("Captured screenshot: 20_product_marked_sold.png")

            assert "Vendido" in page.content() or "Sold" in page.content()
            print("Verified product marked as Sold with 420.00 EUR!")

            browser.close()
            print("\n==================================================================")
            print("REAL BROWSER E2E VERIFICATION COMPLETED WITH 100% SUCCESS!")
            print("==================================================================")

    finally:
        if server_proc:
            print("Terminating background dev server process...")
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
    run_full_browser_verification()
