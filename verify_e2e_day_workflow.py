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
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        import django
        django.setup()
        from inventory.models import MarketplaceSite, ProductListingLink
        MarketplaceSite.objects.filter(name="Vestiaire Collective").delete()
        ProductListingLink.objects.all().delete()

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

            console_messages = []
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

            network_failures = []
            page.on("requestfailed", lambda req: network_failures.append(f"FAILED: {req.method} {req.url} - {req.failure}") if BASE_URL in req.url else None)
            page.on("response", lambda resp: network_failures.append(f"HTTP {resp.status}: {resp.url}") if resp.status >= 400 and BASE_URL in resp.url and "/admin/" not in resp.url and "favicon" not in resp.url else None)

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
            page.fill('input[type="text"][name="q"]', "Schott")
            page.press('input[type="text"][name="q"]', "Enter")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "11_dashboard_search_schott.png"))
            print("Captured screenshot: 11_dashboard_search_schott.png")
            assert "Schott" in page.content(), "Expected search results containing 'Schott'"

            # 4.4 Date Search
            print("[4.4] Testing flexible date search ('2026-10')...")
            page.fill('input[type="text"][name="q"]', "2026-10")
            page.press('input[type="text"][name="q"]', "Enter")
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

            # 5.5b Test Dashboard Marketplace Platform Selector
            print("[5.5b] Testing Dashboard Marketplace Platform Filter with both Wallapop & Vinted...")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")
            platform_select = page.locator('select[name="platform"]')
            assert platform_select.is_visible(), "Expected platform filter select to be visible"
            options_text = platform_select.inner_text()
            assert "Wallapop" in options_text
            assert "Vinted" in options_text
            assert "Milanuncios" not in options_text, "Milanuncios has 0 products and must NOT appear in selector"
            assert "eBay" not in options_text, "eBay has 0 products and must NOT appear in selector"
            print("Verified only platforms with published products (Wallapop, Vinted) appear in selector!")

            # Filter by Wallapop
            page.locator('select[name="platform"]').select_option("wallapop")
            page.locator('#platformFilterForm').evaluate("f => f.submit()")
            page.wait_for_url(lambda url: "platform=wallapop" in url)
            page.wait_for_load_state("networkidle")
            assert "platform=wallapop" in page.url
            page.screenshot(path=str(SCREENSHOTS_DIR / "21_dashboard_platform_filter_wallapop.png"))
            print("Captured screenshot: 21_dashboard_platform_filter_wallapop.png")
            assert "Schott" in page.content()

            # Return to detail page to test removal
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

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

            # 5.6b Verify Vinted dynamically disappeared from selector
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")
            options_after = page.locator('select[name="platform"]').inner_text()
            assert "Vinted" not in options_after, "Vinted has 0 published products and should no longer appear in selector"
            print("Verified Vinted dynamically disappeared from selector after link deletion!")
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")

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

            # ==============================================================
            # PHASE 8: MULTI-PRODUCT MARKETPLACE LINKS & COMBINED FILTERS
            # ==============================================================
            print("\n--- PHASE 8: Multi-Product Marketplace Links & Combined Filters ---")

            from inventory.models import Product

            # Product 1 is Schott jacket (detail_url, marked Sold)
            # Re-add Vinted link to Product 1 via UI
            print("[8.1] Re-adding Vinted link to Product 1 (Schott - Sold)...")
            page.goto(detail_url)
            page.wait_for_load_state("networkidle")
            vinted_card_p1 = page.locator('div[data-site-slug="vinted"]')
            vinted_card_p1.locator('input[name="url"]').fill("https://www.vinted.es/items/schott-biker-sold-p1")
            vinted_card_p1.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            assert "schott-biker-sold-p1" in page.content()
            print("Product 1 now has Wallapop (Sold) and Vinted (Sold).")

            # Select 4 distinct other products from inventory
            p1_id = int(detail_url.rstrip("/").split("/")[-1])
            other_products = list(Product.objects.exclude(id=p1_id).order_by("id")[:4])
            p2 = other_products[0]
            p3 = other_products[1]
            p4 = other_products[2]
            p5 = other_products[3]

            # Ensure initial statuses for p2, p3, p4, p5
            p2.is_sold = False
            p2.save()
            p3.is_sold = False
            p3.save()
            p4.is_sold = False
            p4.save()
            p5.is_sold = False
            p5.save()

            # Product 2 (Active): Add Wallapop and Milanuncios links
            print(f"[8.2] Adding Wallapop & Milanuncios links to Product 2 (ID {p2.id} - Active)...")
            page.goto(f"{BASE_URL}/products/{p2.id}/")
            page.wait_for_load_state("networkidle")
            card_p2_wallapop = page.locator('div[data-site-slug="wallapop"]')
            card_p2_wallapop.locator('input[name="url"]').fill(f"https://es.wallapop.com/item/prod-{p2.id}-wallapop")
            card_p2_wallapop.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")

            card_p2_milanuncios = page.locator('div[data-site-slug="milanuncios"]')
            card_p2_milanuncios.locator('input[name="url"]').fill(f"https://www.milanuncios.com/moda/prod-{p2.id}-milanuncios.htm")
            card_p2_milanuncios.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            print("Product 2 configured with Wallapop and Milanuncios (Active).")

            # Product 3 (Active): Add Vinted and eBay links
            print(f"[8.3] Adding Vinted & eBay links to Product 3 (ID {p3.id} - Active)...")
            page.goto(f"{BASE_URL}/products/{p3.id}/")
            page.wait_for_load_state("networkidle")
            card_p3_vinted = page.locator('div[data-site-slug="vinted"]')
            card_p3_vinted.locator('input[name="url"]').fill(f"https://www.vinted.es/items/prod-{p3.id}-vinted")
            card_p3_vinted.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")

            card_p3_ebay = page.locator('div[data-site-slug="ebay"]')
            card_p3_ebay.locator('input[name="url"]').fill(f"https://www.ebay.es/itm/prod-{p3.id}-ebay")
            card_p3_ebay.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            print("Product 3 configured with Vinted and eBay (Active).")

            # Product 4 (Sold): Add eBay link and mark as Sold via form
            print(f"[8.4] Adding eBay link and marking Product 4 (ID {p4.id}) as Sold...")
            page.goto(f"{BASE_URL}/products/{p4.id}/")
            page.wait_for_load_state("networkidle")
            card_p4_ebay = page.locator('div[data-site-slug="ebay"]')
            card_p4_ebay.locator('input[name="url"]').fill(f"https://www.ebay.es/itm/prod-{p4.id}-ebay-sold")
            card_p4_ebay.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")

            page.fill('input[name="sale_price"]', "150.00")
            sold_box_p4 = page.locator('input[name="is_sold"]')
            if not sold_box_p4.is_checked():
                sold_box_p4.check()
            page.locator('form:has(input[name="sale_price"]) button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            assert "Vendido" in page.content() or "Sold" in page.content()
            print("Product 4 configured with eBay and marked Sold.")

            # Product 5 (Active): Add Milanuncios link
            print(f"[8.5] Adding Milanuncios link to Product 5 (ID {p5.id} - Active)...")
            page.goto(f"{BASE_URL}/products/{p5.id}/")
            page.wait_for_load_state("networkidle")
            card_p5_milanuncios = page.locator('div[data-site-slug="milanuncios"]')
            card_p5_milanuncios.locator('input[name="url"]').fill(f"https://www.milanuncios.com/moda/prod-{p5.id}-milanuncios")
            card_p5_milanuncios.locator('button[type="submit"]:has-text("Guardar Enlace"), button[type="submit"]:has-text("Save Link")').click()
            page.wait_for_load_state("networkidle")
            print("Product 5 configured with Milanuncios (Active).")

            # ==============================================================
            # TEST COMBINED CONDITIONS ON DASHBOARD
            # ==============================================================
            print("\n--- Testing Combined Filter Conditions on Dashboard ---")

            # 8.6 Inspect Platform Dropdown
            print("[8.6] Verifying platform filter dropdown options...")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")
            platform_select = page.locator('select[name="platform"]')
            assert platform_select.is_visible()
            opts_text = platform_select.inner_text()
            print(f"Dropdown options text: {opts_text}")
            assert "Wallapop (2)" in opts_text
            assert "Vinted (2)" in opts_text
            assert "Milanuncios (2)" in opts_text
            assert "eBay (2)" in opts_text
            assert "Vestiaire Collective" not in opts_text
            page.screenshot(path=str(SCREENSHOTS_DIR / "22_dashboard_filter_selector_populated.png"))
            print("Captured screenshot: 22_dashboard_filter_selector_populated.png")

            # 8.7 Condition: platform=wallapop + status=all
            print("[8.7] Testing combined condition: platform=wallapop, status=all...")
            platform_select.select_option("wallapop")
            page.locator('#platformFilterForm').evaluate("f => f.submit()")
            page.wait_for_url(lambda u: "platform=wallapop" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "23_dashboard_combined_wallapop_all.png"))
            print("Captured screenshot: 23_dashboard_combined_wallapop_all.png")

            # Check counters
            tabs_text = page.locator('a[href*="status="], a[href*="status=active"], a[href*="status=sold"]').all_inner_texts()
            full_tabs_text = " ".join(tabs_text)
            print(f"Status counters on wallapop=all: {full_tabs_text}")
            assert "(2)" in full_tabs_text  # Total
            assert "(1)" in full_tabs_text  # Active & Sold

            # Check displayed cards count: exactly 2
            cards_count = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for wallapop all: {cards_count}")
            assert cards_count == 2

            # 8.8 Condition: platform=wallapop + status=active
            print("[8.8] Testing combined condition: platform=wallapop, status=active...")
            active_tab = page.locator('a[href*="status=active"]').first
            active_tab.click()
            page.wait_for_url(lambda u: "status=active" in u and "platform=wallapop" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "24_dashboard_combined_wallapop_active.png"))
            print("Captured screenshot: 24_dashboard_combined_wallapop_active.png")

            cards_active = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for wallapop active: {cards_active}")
            assert cards_active == 1
            # Product 1 (Schott - Sold) should not appear
            assert "Schott" not in page.locator(".grid").inner_text()

            # 8.9 Condition: platform=wallapop + status=sold
            print("[8.9] Testing combined condition: platform=wallapop, status=sold...")
            sold_tab = page.locator('a[href*="status=sold"]').first
            sold_tab.click()
            page.wait_for_url(lambda u: "status=sold" in u and "platform=wallapop" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "25_dashboard_combined_wallapop_sold.png"))
            print("Captured screenshot: 25_dashboard_combined_wallapop_sold.png")

            cards_sold = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for wallapop sold: {cards_sold}")
            assert cards_sold == 1
            # Product 1 (Schott) SHOULD appear
            assert "Schott" in page.locator(".grid").inner_text()

            # 8.10 Condition: platform=milanuncios + status=sold (Empty state check)
            print("[8.10] Testing combined condition: platform=milanuncios, status=sold (expecting 0)...")
            page.locator('select[name="platform"]').select_option("milanuncios")
            page.locator('#platformFilterForm').evaluate("f => f.submit()")
            page.wait_for_url(lambda u: "platform=milanuncios" in u and "status=sold" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "26_dashboard_combined_milanuncios_sold_empty.png"))
            print("Captured screenshot: 26_dashboard_combined_milanuncios_sold_empty.png")

            cards_mil_sold = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for milanuncios sold: {cards_mil_sold}")
            assert cards_mil_sold == 0
            page_text = page.content()
            assert "No se encontraron productos" in page_text or "No products found" in page_text

            # 8.11 Condition: platform=milanuncios + status=active
            print("[8.11] Testing combined condition: platform=milanuncios, status=active...")
            page.locator('a[href*="status=active"]').first.click()
            page.wait_for_url(lambda u: "status=active" in u and "platform=milanuncios" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "27_dashboard_combined_milanuncios_active.png"))
            print("Captured screenshot: 27_dashboard_combined_milanuncios_active.png")

            cards_mil_active = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for milanuncios active: {cards_mil_active}")
            assert cards_mil_active == 2

            # 8.12 Condition: platform=vinted + search q=Schott
            print("[8.12] Testing combined condition: platform=vinted, search q=Schott...")
            page.goto(f"{BASE_URL}/dashboard/?platform=vinted")
            page.wait_for_load_state("networkidle")

            search_input = page.locator('input[type="text"][name="q"]')
            search_input.fill("Schott")
            search_input.press("Enter")
            page.wait_for_url(lambda u: "platform=vinted" in u and "q=Schott" in u)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "28_dashboard_combined_vinted_search_schott.png"))
            print("Captured screenshot: 28_dashboard_combined_vinted_search_schott.png")

            # Check that input retained 'Schott' and dropdown retained 'vinted'
            assert page.locator('input[type="text"][name="q"]').input_value() == "Schott"
            assert page.locator('select[name="platform"]').input_value() == "vinted"
            assert "Schott" in page.locator(".grid").inner_text()

            # 8.13 Condition: platform=ebay + status=sold
            print("[8.13] Testing combined condition: platform=ebay, status=sold...")
            page.goto(f"{BASE_URL}/dashboard/?platform=ebay&status=sold")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "29_dashboard_combined_ebay_sold.png"))
            print("Captured screenshot: 29_dashboard_combined_ebay_sold.png")

            cards_ebay_sold = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible for ebay sold: {cards_ebay_sold}")
            assert cards_ebay_sold == 1

            # 8.14 Reset platform filter to 'All platforms'
            print("[8.14] Resetting platform filter to All Platforms...")
            page.goto(f"{BASE_URL}/dashboard/?platform=ebay")
            page.wait_for_load_state("networkidle")
            page.locator('select[name="platform"]').select_option("")
            page.locator('#platformFilterForm').evaluate("f => f.submit()")
            page.wait_for_url(lambda u: "platform=" not in u or "platform=&" in u or u.endswith("platform="))
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "30_dashboard_filter_reset_all_platforms.png"))
            print("Captured screenshot: 30_dashboard_filter_reset_all_platforms.png")

            cards_reset = page.locator(".grid > div, .grid > a").count()
            print(f"Cards visible after resetting filter: {cards_reset}")
            assert cards_reset >= 20

            # 8.15 DevTools Console & Network Audit
            print("\n[8.15] Auditing DevTools console logs and network traffic...")
            print(f"Captured console messages: {len(console_messages)}")
            critical_console_errors = [
                c for c in console_messages
                if "error" in c.lower()
                and "favicon" not in c.lower()
                and "status of 404" not in c.lower()
                and "status of 403" not in c.lower()
            ]
            print(f"Console errors: {critical_console_errors}")
            assert len(critical_console_errors) == 0, f"Found unexpected console errors: {critical_console_errors}"

            print(f"Network failures: {network_failures}")
            assert len(network_failures) == 0, f"Found network failures: {network_failures}"
            print("DevTools console & network audit passed with 0 errors!")

            browser.close()
            print("\n==================================================================")
            print("REAL BROWSER E2E VERIFICATION COMPLETED WITH 100% SUCCESS!")
            print("==================================================================")

    finally:
        for sample_p in ["sample_leather_jacket_front.jpg", "sample_leather_jacket_detail.jpg"]:
            try:
                Path(sample_p).unlink(missing_ok=True)
            except Exception:
                pass
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
