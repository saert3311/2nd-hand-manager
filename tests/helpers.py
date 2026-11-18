"""Shared test helpers for Django unit/integration tests and Playwright browser suites."""

import io
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

User = get_user_model()


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
    """Launch system Chrome when installed, falling back seamlessly to Playwright Chromium."""
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
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


def abort_nonessential_fonts(page):
    """Abort external webfont and analytics requests so offline/headless Playwright loads stay deterministic."""
    blocked_hosts = (
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "googletagmanager.com",
        "google-analytics.com",
    )
    page.route(
        "**/*",
        lambda route: route.abort() if any(host in route.request.url for host in blocked_hosts) else route.continue_(),
    )


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
