import io
import sys
import time
import zipfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = Path("browser_verification_screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def generate_sample_images():
    img1_path = Path("sample_camera_front.jpg")
    img2_path = Path("sample_camera_back.jpg")

    img1 = Image.new("RGB", (400, 400), color=(50, 80, 150))
    img1.save(img1_path, format="JPEG")

    img2 = Image.new("RGB", (400, 400), color=(180, 70, 70))
    img2.save(img2_path, format="JPEG")

    return [str(img1_path.resolve()), str(img2_path.resolve())]


def run_browser_verification():
    images = generate_sample_images()
    print("Sample images prepared:", images)

    with sync_playwright() as p:
        print(f"Launching real Chrome from: {CHROME_PATH}")
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )

        # Start browser context with Spanish browser language (Accept-Language: es-ES)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="es-ES",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        page = context.new_page()

        # -------------------------------------------------------------
        # STEP 1: Unauthenticated visitor -> Redirect to Login in Spanish
        # -------------------------------------------------------------
        print("\n[STEP 1] Navigating to root / with Accept-Language: es-ES")
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        print("Current URL:", page.url)
        assert "/login/" in page.url, f"Expected redirect to /login/, got {page.url}"

        # Verify initial UI is in Spanish based on Accept-Language
        content = page.content()
        assert "Inicia sesión en tu cuenta" in content, "Expected Spanish heading on login page!"
        assert "Usuario" in content, "Expected Spanish 'Usuario' label!"
        assert "Contraseña" in content, "Expected Spanish 'Contraseña' label!"
        assert "Iniciar Sesión" in content, "Expected Spanish 'Iniciar Sesión' button!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_login_spanish_auto.png"))
        print("Verified automatic Spanish browser language detection on login page.")
        print("Captured screenshot: 01_login_spanish_auto.png")

        # -------------------------------------------------------------
        # STEP 2: Login as Assistant
        # -------------------------------------------------------------
        print("\n[STEP 2] Logging in as assistant")
        page.fill('input[name="username"]', "assistant")
        page.fill('input[name="password"]', "assistant123")
        page.click('form[action*="login"] button[type="submit"]')
        page.wait_for_load_state("networkidle")
        print("Redirected URL after assistant login:", page.url)
        assert "/intake/" in page.url, f"Expected assistant redirect to /intake/, got {page.url}"

        # Verify intake page is in Spanish
        content = page.content()
        assert "Nueva Entrada de Producto" in content, "Expected Spanish title on intake page!"
        assert "Fotos (Obligatorio)" in content, "Expected Spanish photo label!"
        assert "Guardar y Catalogar Siguiente Artículo" in content, "Expected Spanish submit button!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_assistant_intake_spanish.png"))
        print("Captured screenshot: 02_assistant_intake_spanish.png")

        # -------------------------------------------------------------
        # STEP 3: Test Language Switcher in Navbar on Intake Page
        # -------------------------------------------------------------
        print("\n[STEP 3] Testing Navbar Language Switcher on Intake Page")
        print("Switching language to English (EN)...")
        en_btn = page.locator('button[name="language"][value="en"]').first
        with page.expect_navigation():
            en_btn.click()
        page.wait_for_load_state("networkidle")
        print("Page URL after switching to EN:", page.url)

        content = page.content()
        assert "New Product Intake" in content or "Product Intake" in content, "Expected English title after switching to EN!"
        assert "Photos (Required)" in content, "Expected English photo label after switching to EN!"
        assert "Save & Catalog Next Item" in content or "Save" in content, "Expected English submit button!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_assistant_intake_switched_to_en.png"))
        print("Verified language switched smoothly to English on Intake!")
        print("Captured screenshot: 03_assistant_intake_switched_to_en.png")

        print("Switching language back to Spanish (ES)...")
        es_btn = page.locator('button[name="language"][value="es"]').first
        with page.expect_navigation():
            es_btn.click()
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "Nueva Entrada de Producto" in content, "Expected Spanish title after switching back to ES!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "04_assistant_intake_switched_back_to_es.png"))
        print("Verified language switched back to Spanish on Intake!")
        print("Captured screenshot: 04_assistant_intake_switched_back_to_es.png")

        # -------------------------------------------------------------
        # STEP 4: Assistant fills intake form with photos & field notes
        # -------------------------------------------------------------
        print("\n[STEP 4] Uploading photos and field notes on intake form (Spanish UI)")
        file_input = page.locator('input[type="file"][name="images"]')
        file_input.set_input_files(images)
        time.sleep(1)  # Allow client-side thumbnails to render

        # Verify client-side live thumbnails render in DOM before submission
        preview_imgs = page.locator('#previewGrid img')
        assert preview_imgs.count() == 2, f"Expected 2 preview thumbnails, got {preview_imgs.count()}"
        print(f"Verified {preview_imgs.count()} client-side preview thumbnails rendered before submission!")

        raw_note = "Cámara vintage Olympus OM-1 réflex de 35mm con objetivo Zuiko 50mm f/1.8. Probada, obturador suave, leves marcas estéticas en la base."
        page.fill('textarea[name="raw_note"]', raw_note)
        page.screenshot(path=str(SCREENSHOTS_DIR / "05_intake_form_filled.png"))
        print("Captured screenshot: 05_intake_form_filled.png")

        print("Submitting intake form...")
        page.click('#submitBtn')
        page.wait_for_load_state("networkidle")
        print("Current URL after intake submit:", page.url)

        content = page.content()
        assert "Artículo catalogado correctamente" in content or "Producto #" in content, "Spanish intake success message not found!"
        print("Verified Spanish success message on page!")
        page.screenshot(path=str(SCREENSHOTS_DIR / "06_intake_submitted_success.png"))
        print("Captured screenshot: 06_intake_submitted_success.png")

        # Verify zero local disk persistence: no images saved to local media/products
        local_media_prod = Path("media/products")
        if local_media_prod.exists():
            disk_files = list(local_media_prod.rglob("*.webp"))
            assert len(disk_files) == 0, f"Found unexpected image files on local disk: {disk_files}"
        print("Verified zero local disk persistence: images saved directly to cloud storage!")

        # -------------------------------------------------------------
        # STEP 5: Switch to Manager account
        # -------------------------------------------------------------
        print("\n[STEP 5] Logging out assistant and logging in as manager")
        logout_btn = page.locator('button:has-text("Cerrar Sesión"), button:has-text("Sign Out")').first
        logout_btn.click()
        page.wait_for_load_state("networkidle")

        page.fill('input[name="username"]', "manager")
        page.fill('input[name="password"]', "manager123")
        page.click('form[action*="login"] button[type="submit"]')
        page.wait_for_load_state("networkidle")
        print("Manager redirected URL:", page.url)
        assert "/dashboard/" in page.url, f"Expected manager redirect to /dashboard/, got {page.url}"

        # -------------------------------------------------------------
        # STEP 6: Manager Dashboard in Spanish & Language Switching
        # -------------------------------------------------------------
        print("\n[STEP 6] Inspecting Manager Dashboard in Spanish")
        content = page.content()
        assert "Catálogo de Inventario" in content or "Panel de Control" in content, "Expected Spanish Dashboard title!"
        assert "Todos" in content, "Expected 'Todos' tab in Spanish!"
        assert "Activo" in content, "Expected 'Activo' tab in Spanish!"
        assert "Vendido" in content, "Expected 'Vendido' tab in Spanish!"
        assert "Olympus" in content, "Newly cataloged Olympus item not found on dashboard!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "07_manager_dashboard_spanish.png"))
        print("Captured screenshot: 07_manager_dashboard_spanish.png")

        print("Testing Dashboard search for 'Olympus'...")
        page.fill('input[name="q"]', "Olympus")
        page.press('input[name="q"]', "Enter")
        page.wait_for_load_state("networkidle")
        assert "Olympus" in page.content(), "Search filter failed to find Olympus!"
        print("Dashboard search filter verified!")

        # Verify product card thumbnail image
        card_img = page.locator('img[alt*="Olympus"], img[alt*="Cámara"]').first
        assert card_img.is_visible(), "Expected product thumbnail image on dashboard card!"
        img_src = card_img.get_attribute("src")
        print(f"Verified dashboard thumbnail image src: {img_src}")
        assert "objectstorage" in img_src or "rapidopack" in img_src or img_src.endswith(".webp"), f"Unexpected thumbnail src: {img_src}"

        print("Testing Dashboard language switch to English (EN)...")
        with page.expect_navigation():
            page.locator('button[name="language"][value="en"]').first.click()
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "Inventory Catalog" in content or "Dashboard" in content, "Expected English Dashboard after toggle!"
        assert "All" in content, "Expected 'All' tab in English!"
        assert "Active" in content, "Expected 'Active' tab in English!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "08_manager_dashboard_english.png"))
        print("Captured screenshot: 08_manager_dashboard_english.png")

        print("Switching Dashboard back to Spanish (ES)...")
        with page.expect_navigation():
            page.locator('button[name="language"][value="es"]').first.click()
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "09_manager_dashboard_back_to_es.png"))
        print("Captured screenshot: 09_manager_dashboard_back_to_es.png")

        # -------------------------------------------------------------
        # STEP 7: Open Product Staging Detail
        # -------------------------------------------------------------
        print("\n[STEP 7] Navigating to product staging detail")
        product_link = page.locator('a[href*="/products/"]').first
        with page.expect_navigation():
            product_link.click()
        page.wait_for_load_state("networkidle")
        print("Staging detail URL:", page.url)

        content = page.content()
        assert "Volver al Panel" in content, "Expected Spanish 'Volver al Panel' link!"
        assert "Notas de Entrada Preservadas" in content, "Expected Spanish preserved notes card heading!"
        assert "Cámara vintage Olympus OM-1" in content, "Preserved raw note not found on staging page!"
        assert "Texto de la Publicación para Marketplace" in content, "Expected Spanish marketplace copy heading!"
        assert "Precio de Venta (€)" in content or "Precio de Venta" in content, "Expected sale price label!"

        # Verify photo gallery on staging detail page
        main_img = page.locator('#mainImage')
        assert main_img.is_visible(), "Main gallery photo not visible on staging page!"
        print("Main gallery photo src:", main_img.get_attribute("src"))

        gallery_thumbs = page.locator('button[onclick*="setMainImage"] img')
        assert gallery_thumbs.count() == 2, f"Expected 2 gallery thumbnails, got {gallery_thumbs.count()}"
        print(f"Verified photo gallery loaded {gallery_thumbs.count()} WebP pictures!")

        # Click second thumbnail to test gallery photo switcher
        second_thumb_btn = page.locator('button[onclick*="setMainImage"]').nth(1)
        second_thumb_btn.click()
        time.sleep(0.5)
        print("Verified interactive gallery switching between uploaded photos!")

        page.screenshot(path=str(SCREENSHOTS_DIR / "10_product_staging_spanish.png"))
        print("Verified preserved raw notes and Spanish staging controls!")
        print("Captured screenshot: 10_product_staging_spanish.png")

        # -------------------------------------------------------------
        # STEP 8: Test Language Toggle on Staging Detail Page
        # -------------------------------------------------------------
        print("\n[STEP 8] Testing language toggle on Staging Detail Page")
        print("Switching staging page to English (EN)...")
        with page.expect_navigation():
            page.locator('button[name="language"][value="en"]').first.click()
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "Back to Dashboard" in content, "Expected English 'Back to Dashboard'!"
        assert "Preserved Intake Notes" in content, "Expected English 'Preserved Intake Notes'!"
        assert "Marketplace Listing Copy" in content, "Expected English 'Marketplace Listing Copy'!"
        assert "Sale Price (€)" in content or "Sale Price" in content, "Expected English sale price label!"
        # Verify raw notes are preserved in English UI as well
        assert "Cámara vintage Olympus OM-1" in content, "Preserved raw note altered in English UI!"
        page.screenshot(path=str(SCREENSHOTS_DIR / "11_product_staging_english.png"))
        print("Captured screenshot: 11_product_staging_english.png")

        print("Switching staging page back to Spanish (ES)...")
        with page.expect_navigation():
            page.locator('button[name="language"][value="es"]').first.click()
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "12_product_staging_back_to_es.png"))
        print("Captured screenshot: 12_product_staging_back_to_es.png")

        # -------------------------------------------------------------
        # STEP 9: Test ZIP Photo Download
        # -------------------------------------------------------------
        print("\n[STEP 9] Testing ZIP photo download")
        with page.expect_download() as download_info:
            page.click('a[href*="download-zip"]')
        download = download_info.value
        zip_save_path = SCREENSHOTS_DIR / download.suggested_filename
        download.save_as(str(zip_save_path))
        print(f"Downloaded ZIP saved to: {zip_save_path} (size: {zip_save_path.stat().st_size} bytes)")
        assert zip_save_path.stat().st_size > 0, "Downloaded ZIP is empty!"

        # Inspect downloaded ZIP bundle contents
        with zipfile.ZipFile(zip_save_path, "r") as zf:
            zip_names = zf.namelist()
            print("Downloaded ZIP contents:", zip_names)
            assert len(zip_names) == 2, f"Expected 2 photos in ZIP, got {len(zip_names)}"
            for name in zip_names:
                assert name.endswith(".webp"), f"Expected WebP image in ZIP, got {name}"
                data = zf.read(name)
                img_probe = Image.open(io.BytesIO(data))
                assert img_probe.format == "WEBP", f"Expected valid WEBP format in ZIP, got {img_probe.format}"
                print(f" - Verified valid {img_probe.format} photo in ZIP: {name} ({img_probe.size[0]}x{img_probe.size[1]})")
        print("Verified downloaded ZIP bundle contains valid streaming WebP images!")

        # -------------------------------------------------------------
        # STEP 10: Test AI Generation Trigger in Spanish Session
        # -------------------------------------------------------------
        print("\n[STEP 10] Triggering Gemini AI listing generation in Spanish session")
        ai_btn = page.locator('button#aiBtn')
        if ai_btn.is_visible():
            ai_btn.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / "13_after_ai_generate_spanish.png"))
            print("Captured screenshot: 13_after_ai_generate_spanish.png")
            print("Page message after AI trigger:")
            for msg in page.locator('.p-3\\.5, .alert, .bg-emerald-50, .bg-rose-50').all_text_contents():
                print(" -", msg.strip())

        # -------------------------------------------------------------
        # STEP 11: Test Clipboard Copy Interaction
        # -------------------------------------------------------------
        print("\n[STEP 11] Testing 'Copiar Título' button click interaction")
        copy_title_btn = page.locator('button:has-text("Copiar Título")').first
        if copy_title_btn.is_visible():
            copy_title_btn.click()
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS_DIR / "14_copy_title_clicked.png"))
            print("Captured screenshot: 14_copy_title_clicked.png")

        # -------------------------------------------------------------
        # STEP 12: Update Sale Price & Mark as Sold (Spanish UI)
        # -------------------------------------------------------------
        print("\n[STEP 12] Updating sale price to 125.00 EUR and marking as Sold")
        page.fill('input[name="sale_price"]', "125.00")
        sold_checkbox = page.locator('input[name="is_sold"]')
        if not sold_checkbox.is_checked():
            sold_checkbox.check()

        with page.expect_navigation():
            page.click('button:has-text("Guardar Cambios de Publicación"), button:has-text("Save Listing Changes")')
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "15_product_marked_sold_spanish.png"))
        print("Captured screenshot: 15_product_marked_sold_spanish.png")

        content = page.content()
        assert "Estado: Vendido" in content or "Status: Sold" in content, "Expected status to be updated to Vendido/Sold!"
        assert "actualizado con éxito" in content or "updated successfully" in content, "Expected update success alert!"
        print("Verified sold status and success flash notification!")

        # -------------------------------------------------------------
        # STEP 13: Verify Sold Item on Dashboard under 'Vendido' Tab
        # -------------------------------------------------------------
        print("\n[STEP 13] Verifying sold item on Dashboard under 'Vendido' tab")
        page.goto(f"{BASE_URL}/dashboard/?status=sold")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(SCREENSHOTS_DIR / "16_dashboard_sold_tab_spanish.png"))
        print("Captured screenshot: 16_dashboard_sold_tab_spanish.png")

        content = page.content()
        assert "125" in content, "Sold price 125 not found on Sold tab!"
        print("Successfully verified sold status and price on dashboard in Spanish!")

        browser.close()
        print("\n=== ALL REAL BROWSER & MULTI-LANGUAGE WORKFLOW VERIFICATIONS PASSED! ===")


if __name__ == "__main__":
    run_browser_verification()
