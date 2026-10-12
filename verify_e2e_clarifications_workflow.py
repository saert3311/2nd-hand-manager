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
        print(f"[Server] Django server already running at {BASE_URL}")
        return None, None

    print("[Server] Starting Django development server at 127.0.0.1:8000...")
    server_log = open("server_qa.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [r".venv\Scripts\python.exe", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        stdout=server_log,
        stderr=server_log,
        cwd=os.getcwd(),
    )
    for _ in range(30):
        time.sleep(1)
        if is_server_ready(BASE_URL):
            print("[Server] Django server is ready and responding!")
            return proc, server_log
    server_log.close()
    raise RuntimeError("Timed out waiting for Django server to start")


def generate_sample_images():
    img1_path = Path("sample_product_item_a.jpg")
    img2_path = Path("sample_product_item_b.jpg")

    img1 = Image.new("RGB", (600, 600), color=(40, 50, 70))
    img1.save(img1_path, format="JPEG", quality=90)

    img2 = Image.new("RGB", (600, 600), color=(80, 50, 40))
    img2.save(img2_path, format="JPEG", quality=90)

    return [str(img1_path.resolve()), str(img2_path.resolve())]


def run_qa_browser_workflow():
    print("==================================================================")
    print("STARTING REAL BROWSER QA WORKFLOW VERIFICATION (CHROME)")
    print("==================================================================")

    # 1. Setup Django environment and demo roles
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django
    django.setup()
    from django.core.management import call_command
    call_command("setup_roles")
    from inventory.models import Product, ProductClarification
    ProductClarification.objects.all().delete()
    Product.objects.filter(raw_note__contains="Schott").delete()
    Product.objects.filter(raw_note__contains="Burberry").delete()
    Product.objects.filter(raw_note__contains="Nike").delete()

    server_proc, server_log = start_server_if_needed()

    try:
        sample_photos = generate_sample_images()
        print("Generated sample photos for intake.")

        with sync_playwright() as p:
            print(f"Launching Google Chrome from: {CHROME_PATH}")
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

            # -------------------------------------------------------------
            # STEP 1: ASSISTANT DAILY INTAKE WORKFLOW
            # -------------------------------------------------------------
            print("\n[Step 1] Assistant Login & Products Intake...")
            page.goto(f"{BASE_URL}/login/")
            page.wait_for_load_state("networkidle")
            page.fill('input[name="username"]', "assistant")
            page.fill('input[name="password"]', "assistant123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")
            assert "/intake/" in page.url, f"Expected redirect to /intake/, got {page.url}"

            # Verify no pending doubts badge or banner initially
            badge_loc = page.locator("#badge-pending-clarifications")
            banner_loc = page.locator(".alert-pending-clarifications-banner")
            print(f"Initial badge count: {badge_loc.count()}, banner count: {banner_loc.count()}")
            assert badge_loc.count() == 0 or not badge_loc.is_visible(), "Badge should not be visible when no doubts pending"

            # Intake Product 1: Schott 618 Leather Jacket
            print("Intaking Product 1 (Schott 618 Leather Jacket)...")
            page.locator('input[type="file"][name="images"]').set_input_files(sample_photos)
            page.fill('textarea[name="raw_note"]', "Chaqueta biker Schott NYC 618 cuero negro vintage 90s, cremalleras Talon.")
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")
            assert "catalogado" in page.content() or "Producto #" in page.content()

            # Intake Product 2: Burberry Trench Coat
            print("Intaking Product 2 (Burberry Trench Coat)...")
            page.locator('input[type="file"][name="images"]').set_input_files(sample_photos)
            page.fill('textarea[name="raw_note"]', "Gabardina Burberry vintage beige clásica con cinturón y forro nova check.")
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")

            # Intake Product 3: Nike Air Jordan 1
            print("Intaking Product 3 (Nike Air Jordan 1)...")
            page.locator('input[type="file"][name="images"]').set_input_files(sample_photos)
            page.fill('textarea[name="raw_note"]', "Zapatillas Nike Air Jordan 1 Retro 1994 Chicago.")
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")

            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_01_assistant_intake_clean.png"))
            print("Captured screenshot: qa_01_assistant_intake_clean.png")

            # Assistant Logs Out
            page.click('form[action*="logout"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # -------------------------------------------------------------
            # STEP 2: MANAGER STAGING & ASKING CLARIFICATIONS
            # -------------------------------------------------------------
            print("\n[Step 2] Manager Reviews & Submits Clarification Doubts...")
            page.fill('input[name="username"]', "manager")
            page.fill('input[name="password"]', "manager123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")
            assert "/dashboard/" in page.url or "/intake/" in page.url

            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")

            # Retrieve product IDs from DB for precise navigation
            from inventory.models import Product, ProductStatus
            p1 = Product.objects.filter(raw_note__contains="Schott").order_by("-id").first()
            p2 = Product.objects.filter(raw_note__contains="Burberry").order_by("-id").first()
            p3 = Product.objects.filter(raw_note__contains="Nike").order_by("-id").first()
            assert p1 and p2 and p3, "Created products must exist"

            # Open Product 1
            print(f"Manager opening Product 1 (#{p1.id})...")
            page.goto(f"{BASE_URL}/products/{p1.id}/")
            page.wait_for_load_state("networkidle")

            # Verify initial status badge is Draft
            badge_text = page.locator("#product-status-badge").inner_text()
            print(f"Product 1 initial badge: '{badge_text}'")
            assert "borrador" in badge_text.lower() or "draft" in badge_text.lower()

            # Manager asks question 1 (Measurements)
            print("Manager submitting clarification on Product 1 (Measurements)...")
            page.select_option('#clarifications-section select[name="category"]', "measurements")
            page.fill('#clarifications-section textarea[name="question"]', "¿Puedes medir el ancho de sisa a sisa y el largo de manga?")
            page.click('#clarifications-section button[type="submit"]:has-text("Enviar Pregunta"), #clarifications-section button[type="submit"]:has-text("Send Question")')
            page.wait_for_load_state("networkidle")

            p1.refresh_from_db()
            assert p1.status == ProductStatus.AWAITING_INFO, f"Expected AWAITING_INFO, got {p1.status}"

            # Verify UI updates: badge is Awaiting Info, caution gate is visible
            badge_updated = page.locator("#product-status-badge").inner_text()
            assert "dudas" in badge_updated.lower() or "awaiting" in badge_updated.lower()
            assert page.locator(".publishing-gate-caution").is_visible(), "Caution gate must be visible when awaiting info"
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_02_manager_asked_clarification_product1.png"))
            print("Captured screenshot: qa_02_manager_asked_clarification_product1.png")

            # Open Product 2
            print(f"Manager opening Product 2 (#{p2.id})...")
            page.goto(f"{BASE_URL}/products/{p2.id}/")
            page.wait_for_load_state("networkidle")

            # Manager asks question 2 (Material)
            print("Manager submitting clarification on Product 2 (Material)...")
            page.select_option('#clarifications-section select[name="category"]', "material_authenticity")
            page.fill('#clarifications-section textarea[name="question"]', "¿Lleva etiqueta de composición con 100% algodón o mezcla sintética?")
            page.click('#clarifications-section button[type="submit"]:has-text("Enviar Pregunta"), #clarifications-section button[type="submit"]:has-text("Send Question")')
            page.wait_for_load_state("networkidle")

            p2.refresh_from_db()
            assert p2.status == ProductStatus.AWAITING_INFO
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_03_manager_asked_clarification_product2.png"))
            print("Captured screenshot: qa_03_manager_asked_clarification_product2.png")

            # Manager navigates to dashboard
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")

            # Verify badge in navbar shows 2
            nav_badge = page.locator("#badge-pending-clarifications")
            assert nav_badge.is_visible()
            assert "2" in nav_badge.inner_text()

            # Filter dashboard by status=awaiting_info
            page.click('a[href*="status=awaiting_info"]')
            page.wait_for_load_state("networkidle")
            assert "status=awaiting_info" in page.url
            dashboard_content = page.content()
            assert "Schott" in dashboard_content
            assert "Burberry" in dashboard_content
            assert "Nike" not in dashboard_content, "Product 3 (Nike) should NOT appear in awaiting_info filter"
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_04_manager_dashboard_filtered_dudas.png"))
            print("Captured screenshot: qa_04_manager_dashboard_filtered_dudas.png")

            # Manager Logs Out
            page.click('form[action*="logout"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # -------------------------------------------------------------
            # STEP 3: ASSISTANT NOTIFICATIONS & ANSWERS WORKFLOW
            # -------------------------------------------------------------
            print("\n[Step 3] Assistant Notification Alerting & Answering Flow...")
            page.fill('input[name="username"]', "assistant")
            page.fill('input[name="password"]', "assistant123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # Check navbar attention badge
            nav_badge = page.locator("#badge-pending-clarifications")
            assert nav_badge.is_visible()
            assert "2" in nav_badge.inner_text()
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_05_assistant_navbar_notification_badge.png"))
            print("Captured screenshot: qa_05_assistant_navbar_notification_badge.png")

            # Check intake mobile alert banner
            page.goto(f"{BASE_URL}/intake/")
            page.wait_for_load_state("networkidle")
            intake_banner = page.locator(".alert-pending-clarifications-banner")
            assert intake_banner.is_visible()
            assert "2" in intake_banner.inner_text()
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_06_assistant_intake_banner_alert.png"))
            print("Captured screenshot: qa_06_assistant_intake_banner_alert.png")

            # Click banner action button to go to pending doubts
            page.click('.alert-pending-clarifications-banner a[href*="status=awaiting_info"]')
            page.wait_for_load_state("networkidle")
            assert "status=awaiting_info" in page.url

            # Assistant opens Product 1 and answers
            print("Assistant opening Product 1 and submitting answer...")
            page.goto(f"{BASE_URL}/products/{p1.id}/")
            page.wait_for_load_state("networkidle")

            # Answer question
            page.fill('#clarifications-section form[action*="/answer/"] input[name="answer"]', "Medidas: 54 cm sisa a sisa, 63 cm largo de manga.")
            page.click('#clarifications-section form[action*="/answer/"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            p1.refresh_from_db()
            assert p1.status == ProductStatus.READY, f"Product 1 should auto-transition to READY, got {p1.status}"

            badge_text = page.locator("#product-status-badge").inner_text()
            assert "listo" in badge_text.lower() or "ready" in badge_text.lower()
            assert page.locator(".ai-regeneration-callout").is_visible(), "AI regeneration callout must be shown"
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_07_product1_auto_transition_ready.png"))
            print("Captured screenshot: qa_07_product1_auto_transition_ready.png")

            # Check notification counter decremented from 2 to 1
            nav_badge = page.locator("#badge-pending-clarifications")
            assert nav_badge.is_visible()
            assert "1" in nav_badge.inner_text(), f"Expected counter '1', got '{nav_badge.inner_text()}'"

            page.goto(f"{BASE_URL}/intake/")
            page.wait_for_load_state("networkidle")
            intake_banner = page.locator(".alert-pending-clarifications-banner")
            assert intake_banner.is_visible()
            assert "1" in intake_banner.inner_text()
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_08_assistant_counter_decremented_to_1.png"))
            print("Captured screenshot: qa_08_assistant_counter_decremented_to_1.png")

            # Assistant opens Product 2 and answers
            print("Assistant opening Product 2 and submitting answer...")
            page.goto(f"{BASE_URL}/products/{p2.id}/")
            page.wait_for_load_state("networkidle")

            page.fill('#clarifications-section form[action*="/answer/"] input[name="answer"]', "Confirmado: etiqueta 100% algodón gabardina.")
            page.click('#clarifications-section form[action*="/answer/"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            p2.refresh_from_db()
            assert p2.status == ProductStatus.READY
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_09_product2_auto_transition_ready.png"))
            print("Captured screenshot: qa_09_product2_auto_transition_ready.png")

            # Verify all pending doubts resolved: navbar badge and intake banner gone
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")
            assert page.locator("#badge-pending-clarifications").count() == 0, "Navbar badge must not exist when count is 0"

            page.goto(f"{BASE_URL}/intake/")
            page.wait_for_load_state("networkidle")
            assert page.locator(".alert-pending-clarifications-banner").count() == 0, "Intake banner must not exist when count is 0"
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_10_notifications_cleared.png"))
            print("Captured screenshot: qa_10_notifications_cleared.png")

            # Assistant Logs Out
            page.click('form[action*="logout"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # -------------------------------------------------------------
            # STEP 4: MANAGER FINAL STAGING, SALES & BLOCKING
            # -------------------------------------------------------------
            print("\n[Step 4] Manager Final Staging, Status Gating & Sale Tracking...")
            page.fill('input[name="username"]', "manager")
            page.fill('input[name="password"]', "manager123")
            page.click('form[action*="login"] button[type="submit"]')
            page.wait_for_load_state("networkidle")

            # Open Product 1 (Ready)
            page.goto(f"{BASE_URL}/products/{p1.id}/")
            page.wait_for_load_state("networkidle")
            assert page.locator(".publishing-gate-caution").count() == 0, "Caution gate should be GONE when ready"

            # Set price and save listing
            print("Setting price and saving listing copy...")
            page.fill('input[name="sale_price"]', "195.00")
            page.click('button[type="submit"]:has-text("Guardar"), button[type="submit"]:has-text("Save")')
            page.wait_for_load_state("networkidle")

            # Add marketplace listing link for Wallapop
            print("Adding marketplace link for Wallapop...")
            wallapop_form = page.locator('div[data-site-slug="wallapop"] form')
            wallapop_form.locator('input[name="url"]').fill("https://es.wallapop.com/item/schott-618-vintage-991")
            wallapop_form.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            assert "Publicado" in page.content() or "Listed" in page.content()
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_11_manager_product1_ready_with_link.png"))
            print("Captured screenshot: qa_11_manager_product1_ready_with_link.png")

            # Mark Product 1 as SOLD
            print("Marking Product 1 as SOLD...")
            page.check('input[name="is_sold"]')
            page.click('button[type="submit"]:has-text("Guardar"), button[type="submit"]:has-text("Save")')
            page.wait_for_load_state("networkidle")

            p1.refresh_from_db()
            assert p1.is_sold is True
            assert p1.status == ProductStatus.SOLD
            badge_text = page.locator("#product-status-badge").inner_text()
            assert "vendido" in badge_text.lower() or "sold" in badge_text.lower()
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_12_manager_product1_sold.png"))
            print("Captured screenshot: qa_12_manager_product1_sold.png")

            # Open Product 3 (Nike) and mark as BLOCKED
            print("Marking Product 3 as BLOCKED...")
            page.goto(f"{BASE_URL}/products/{p3.id}/")
            page.wait_for_load_state("networkidle")
            page.select_option('select[name="status"]', "blocked")
            page.click('button[type="submit"]:has-text("Guardar"), button[type="submit"]:has-text("Save")')
            page.wait_for_load_state("networkidle")

            p3.refresh_from_db()
            assert p3.status == ProductStatus.BLOCKED
            badge_text = page.locator("#product-status-badge").inner_text()
            assert "bloqueado" in badge_text.lower() or "blocked" in badge_text.lower()
            assert page.locator(".publishing-gate-caution").is_visible(), "Caution gate must be shown when blocked"
            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_13_manager_product3_blocked.png"))
            print("Captured screenshot: qa_13_manager_product3_blocked.png")

            # -------------------------------------------------------------
            # STEP 5: DASHBOARD FILTERING & SCOPED BADGES
            # -------------------------------------------------------------
            print("\n[Step 5] Verifying Dashboard Status & Platform Filters...")
            page.goto(f"{BASE_URL}/dashboard/")
            page.wait_for_load_state("networkidle")

            # Check status tabs present
            dudas_tab = page.locator('a[href*="status=awaiting_info"]').inner_text()
            assert "dudas" in dudas_tab.lower() and "(0)" in dudas_tab
            assert page.locator('a[href*="status=blocked"]').is_visible()
            assert page.locator('a[href*="status=sold"]').is_visible()

            # Filter by Blocked
            page.click('a[href*="status=blocked"]')
            page.wait_for_load_state("networkidle")
            assert "status=blocked" in page.url
            blocked_content = page.content()
            assert "Nike" in blocked_content
            assert "Schott" not in blocked_content

            # Filter by Sold
            page.click('a[href*="status=sold"]')
            page.wait_for_load_state("networkidle")
            assert "status=sold" in page.url
            sold_content = page.content()
            assert "Schott" in sold_content
            assert "Nike" not in sold_content

            # Filter by Platform Wallapop
            page.locator('select[name="platform"]').select_option("wallapop")
            page.locator('#platformFilterForm').evaluate("f => f.submit()")
            page.wait_for_url(lambda url: "platform=wallapop" in url)
            page.wait_for_load_state("networkidle")
            assert "platform=wallapop" in page.url
            platform_content = page.content()
            assert "Schott" in platform_content

            page.screenshot(path=str(SCREENSHOTS_DIR / "qa_14_dashboard_filters_verified.png"))
            print("Captured screenshot: qa_14_dashboard_filters_verified.png")

            # Check console errors
            severe_errors = [
                m for m in console_messages
                if "[error]" in m.lower()
                and "favicon" not in m.lower()
                and "status of 404" not in m.lower()
                and "status of 403" not in m.lower()
            ]
            print(f"\nConsole messages logged: {len(console_messages)}, severe errors: {len(severe_errors)}")
            if severe_errors:
                print("Severe console errors:", severe_errors)
            assert len(severe_errors) == 0, f"Expected 0 severe console errors, got {len(severe_errors)}"

            browser.close()

        print("\n==================================================================")
        print("ALL REAL BROWSER QA WORKFLOW STEPS PASSED SUCCESSFULLY!")
        print("==================================================================")

    finally:
        # Cleanup sample files
        for f in ["sample_product_item_a.jpg", "sample_product_item_b.jpg"]:
            if os.path.exists(f):
                os.remove(f)

        if server_proc:
            print("Terminating Django test server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
        if server_log:
            server_log.close()


if __name__ == "__main__":
    run_qa_browser_workflow()
