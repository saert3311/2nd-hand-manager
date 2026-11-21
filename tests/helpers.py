"""Shared test helpers for Django unit/integration tests and Playwright browser suites."""

import io
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

User = get_user_model()

_BLOCKED_EXTERNAL_HOSTS_RE = re.compile(
    r"^https?://(?:[^/]+\.)?"
    r"(?:fonts\.googleapis\.com|fonts\.gstatic\.com|googletagmanager\.com|google-analytics\.com)"
    r"(?:/|$)"
)
_TAILWIND_CDN_RE = re.compile(r"^https?://cdn\.tailwindcss\.com(?:/.*)?$")
_TAILWIND_CDN_CACHE: dict[str, tuple[int, str, bytes]] = {}


def make_test_image_bytes(size=(120, 120), color="teal", image_format="JPEG"):
    """Return in-memory encoded image bytes for unit and browser upload tests."""
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format=image_format)
    return buf.getvalue()


def make_test_image_file(
    name="test.jpg",
    size=(120, 120),
    color="teal",
    image_format="JPEG",
    content_type="image/jpeg",
):
    """Build a SimpleUploadedFile containing a valid image payload."""
    return SimpleUploadedFile(
        name,
        make_test_image_bytes(size=size, color=color, image_format=image_format),
        content_type=content_type,
    )


def create_user_with_group(username, password="password123", group_name=None, is_staff=False):
    """Create a Django user optionally assigned to an inventory role group."""
    user = User.objects.create_user(username=username, password=password, is_staff=is_staff)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


def create_role_users(prefix="test", password="password123"):
    """Create a standard (manager, assistant) user pair with their Django groups."""
    manager = create_user_with_group(f"{prefix}_manager", password=password, group_name="managers")
    assistant = create_user_with_group(f"{prefix}_assistant", password=password, group_name="assistants")
    return manager, assistant


def get_test_artifact_dir(test_cls, repo_subdir=None):
    """
    Return a temporary directory cleaned up via addClassCleanup unless SAVE_TEST_SCREENSHOTS=1.

    Keeping test screenshots and dummy files in TemporaryDirectory prevents dirtying git-tracked
    folders on every local/CI test run while allowing deliberate regeneration on demand.
    """
    if repo_subdir and os.getenv("SAVE_TEST_SCREENSHOTS") == "1":
        path = Path(settings.BASE_DIR) / repo_subdir
        path.mkdir(parents=True, exist_ok=True)
        return path

    temp_dir = tempfile.TemporaryDirectory()
    test_cls.addClassCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


def launch_test_browser(playwright_instance, headless=True):
    """Launch bundled Playwright Chromium on CI or system Chrome when available locally."""
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    if os.getenv("CI") or os.getenv("PLAYWRIGHT_USE_BUNDLED_CHROMIUM") == "1":
        return playwright_instance.chromium.launch(headless=headless)
    try:
        return playwright_instance.chromium.launch(channel="chrome", headless=headless)
    except Exception:
        return playwright_instance.chromium.launch(headless=headless)


def start_shared_browser(test_cls, headless=True):
    """Start a shared Playwright browser for a StaticLiveServerTestCase class with LIFO cleanup."""
    from playwright.sync_api import sync_playwright

    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    pw = sync_playwright().start()
    test_cls.addClassCleanup(pw.stop)
    browser = launch_test_browser(pw, headless=headless)
    test_cls.addClassCleanup(browser.close)
    return browser


def _handle_tailwind_cdn(route):
    """Cache the Tailwind Play CDN script in memory across pages so CI hits the CDN at most once per run."""
    url = route.request.url
    cached = _TAILWIND_CDN_CACHE.get(url)
    if cached is not None:
        status, content_type, body = cached
        route.fulfill(status=status, content_type=content_type, body=body)
        return
    try:
        resp = route.fetch()
        body = resp.body()
        content_type = resp.headers.get("content-type", "application/javascript")
        if resp.status == 200 and body:
            _TAILWIND_CDN_CACHE[url] = (resp.status, content_type, body)
        route.fulfill(status=resp.status, content_type=content_type, body=body)
    except Exception:
        route.continue_()


def abort_nonessential_fonts(page):
    """Abort external webfont/analytics requests and cache Tailwind Play CDN without intercepting localhost."""
    page.route(_BLOCKED_EXTERNAL_HOSTS_RE, lambda route: route.abort())
    page.route(_TAILWIND_CDN_RE, _handle_tailwind_cdn)


@contextmanager
def open_browser_page(
    browser,
    test_case=None,
    *,
    check_page_errors=True,
    block_service_workers=True,
    failure_name=None,
    **context_kwargs,
):
    """Open an isolated Playwright context and page with font/CDN routing, JS error assertions, and cleanup."""
    context_kwargs.setdefault("service_workers", "block" if block_service_workers else "allow")
    context = browser.new_context(**context_kwargs)
    page = context.new_page()
    abort_nonessential_fonts(page)
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    try:
        yield context, page
        if check_page_errors and test_case is not None:
            test_case.assertEqual(page_errors, [], f"Unexpected browser JS errors: {page_errors}")
    except Exception:
        failure_dir = os.getenv("PLAYWRIGHT_FAILURE_DIR", "").strip()
        if failure_dir:
            try:
                raw_name = failure_name or (test_case.id() if test_case is not None else "browser_failure")
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("_") or "browser_failure"
                out_dir = Path(failure_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out_dir / f"{safe_name}_failure.png"), full_page=True)
            except Exception:
                pass
        raise
    finally:
        context.close()


def login_in_browser(
    page,
    live_server_url,
    username,
    password="password123",
    expected_url_pattern="**/dashboard/**",
    wait_until="domcontentloaded",
    navigate_to_login=True,
):
    """Sign in via /login/ and deterministically wait for the post-login redirect URL."""
    if navigate_to_login:
        resp = page.goto(f"{live_server_url}{reverse('inventory:login')}", wait_until=wait_until)
        if resp is None or resp.status != 200:
            status = resp.status if resp is not None else None
            raise AssertionError(f"GET /login/ failed: status={status} url={page.url}")

    page.wait_for_selector("#id_username", timeout=10000)
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("#loginSubmitBtn")
    try:
        page.wait_for_url(expected_url_pattern, wait_until=wait_until, timeout=15000)
    except Exception as exc:
        alert_text = ""
        current_url = ""
        title_text = ""
        try:
            current_url = page.url
            title_text = page.title()
            alerts = page.locator('[role="alert"]')
            if alerts.count() > 0:
                alert_text = alerts.first.inner_text().strip()
        except Exception:
            pass
        raise AssertionError(
            f"Login failed for user={username!r}: url={current_url!r}, "
            f"title={title_text!r}, alert={alert_text!r}"
        ) from exc

    if "/login/" in page.url:
        raise AssertionError(f"Still on login page after submit for user={username!r}: url={page.url!r}")


def goto_authenticated(page, url, wait_until="domcontentloaded"):
    """Navigate to an authenticated route and fail immediately on auth redirects or non-200 HTTP errors."""
    resp = page.goto(url, wait_until=wait_until)
    status = resp.status if resp is not None else None
    if status != 200 or "/login/" in page.url:
        raise AssertionError(
            f"Authenticated navigation to {url!r} failed: status={status}, "
            f"landed_url={page.url!r}, title={page.title()!r}"
        )
    return resp


def assert_visible_images_loaded(test_case, page, selector="img"):
    """Verify every visible matching <img> rendered cleanly without broken media URLs."""
    broken = page.evaluate(
        """(sel) => {
            const imgs = Array.from(document.querySelectorAll(sel));
            return imgs
                .filter((img) => {
                    const style = window.getComputedStyle(img);
                    const rect = img.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                })
                .filter((img) => !img.complete || img.naturalWidth === 0)
                .map((img) => img.getAttribute('src') || img.outerHTML.slice(0, 80));
        }""",
        selector,
    )
    test_case.assertEqual(broken, [], f"Broken or 404 visible images found: {broken}")
