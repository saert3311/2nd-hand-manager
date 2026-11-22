from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from storages.backends.s3 import S3Storage

from inventory.models import Product, ProductImage
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.ai_service import ProductListingSchema, generate_product_listing
from inventory.services.image_service import process_and_convert_to_webp
from inventory.services.storage import OCIObjectStorage
from tests.helpers import make_test_image_bytes, make_test_image_file


class OCIObjectStorageBackendTests(TestCase):
    """
    Unit tests for the OCIObjectStorage backend class and configuration defaults.
    """

    def test_oci_storage_defaults(self):
        storage = OCIObjectStorage(
            bucket_name="test-bucket",
            access_key="test-access-key",
            secret_key="test-secret-key",
            endpoint_url="https://testnamespace.compat.objectstorage.eu-madrid-1.oraclecloud.com",
            region_name="eu-madrid-1",
        )
        self.assertIsNone(storage.default_acl)
        self.assertEqual(storage.signature_version, "s3v4")
        self.assertEqual(storage.addressing_style, "path")
        self.assertFalse(storage.file_overwrite)
        self.assertFalse(storage.querystring_auth)
        self.assertFalse(storage.client_config.s3["payload_signing_enabled"])
        self.assertEqual(storage.client_config.request_checksum_calculation, "when_required")
        self.assertEqual(storage.client_config.response_checksum_validation, "when_required")

    def test_oci_storage_inherits_from_modern_s3_storage(self):
        self.assertTrue(issubclass(OCIObjectStorage, S3Storage))

    def test_oci_storage_url_generation(self):
        storage = OCIObjectStorage(
            bucket_name="test-bucket",
            access_key="test-access-key",
            secret_key="test-secret-key",
            endpoint_url="https://testnamespace.compat.objectstorage.eu-madrid-1.oraclecloud.com",
            region_name="eu-madrid-1",
        )
        url = storage.url("products/2026/10/camera_abc123.webp")
        self.assertIn("https://testnamespace.compat.objectstorage.eu-madrid-1.oraclecloud.com/test-bucket/products/2026/10/camera_abc123.webp", url)
        # Verify query string authentication is disabled for public bucket performance
        self.assertNotIn("AWSAccessKeyId=", url)
        self.assertNotIn("Signature=", url)


class StorageDecouplingAndIntakeTests(TestCase):
    """
    Integration tests verifying image storage decoupling from local disk.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import tempfile
        cls.temp_media = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.assistant = User.objects.create_user(username="asst_user", password="password123")
        self.manager = User.objects.create_user(username="mgr_user", password="password123", is_staff=True)

        asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.assistant.groups.add(asst_group)
        self.manager.groups.add(mgr_group)

    def test_image_service_and_product_image_save_to_storage_not_local_disk(self):
        with self.settings(
            MEDIA_ROOT=self.temp_media,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        ):
            uploaded = make_test_image_file(name="jacket.jpg", size=(120, 120), color="blue")
            webp_file = process_and_convert_to_webp(uploaded)

            product = Product.objects.create(raw_note="Vintage windbreaker", created_by=self.assistant)
            prod_img = ProductImage.objects.create(product=product, image=webp_file, order=0)

            # Check that file can be opened and read from storage
            with prod_img.image.open("rb") as f:
                data = f.read()
                self.assertGreater(len(data), 0)

            # Verify no file is stored in local MEDIA_ROOT / 'products'
            local_products_dir = Path(self.temp_media) / "products"
            if local_products_dir.exists():
                local_files = list(local_products_dir.rglob("*.webp"))
                self.assertEqual(len(local_files), 0, f"Found unexpected files on local disk: {local_files}")
            else:
                # The directory was not even created on disk
                self.assertFalse(local_products_dir.exists())

    def test_intake_view_uploads_directly_to_storage(self):
        with self.settings(
            MEDIA_ROOT=self.temp_media,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        ):
            self.client.login(username="asst_user", password="password123")

            img1 = make_test_image_file(name="photo1.jpg", size=(120, 120), color="red")
            img2 = make_test_image_file(name="photo2.jpg", size=(120, 120), color="green")

            resp = self.client.post(
                reverse("inventory:intake"),
                {
                    "raw_note": "Sony Walkman WM-D6C Cassette Player",
                    "images": [img1, img2],
                },
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)

            product = Product.objects.get(raw_note="Sony Walkman WM-D6C Cassette Player")
            self.assertEqual(product.images.count(), 2)

            for img_record in product.images.all():
                self.assertTrue(img_record.image.name.endswith(".webp"))
                with img_record.image.open("rb") as f:
                    content = f.read()
                    self.assertGreater(len(content), 0)

            # Verify no file was written to local disk
            local_products_dir = Path(self.temp_media) / "products"
            if local_products_dir.exists():
                local_files = list(local_products_dir.rglob("*.webp"))
                self.assertEqual(len(local_files), 0)
            else:
                self.assertFalse(local_products_dir.exists())

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_zip_download_streams_from_storage_backend(self):
        self.client.login(username="mgr_user", password="password123")

        product = Product.objects.create(raw_note="Seiko vintage diver watch")
        ProductImage.objects.create(
            product=product,
            image=ContentFile(make_test_image_bytes(size=(60, 60), color="navy", image_format="WEBP"), name="diver_01.webp"),
            order=0,
        )

        resp = self.client.get(reverse("inventory:download_zip", kwargs={"pk": product.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        self.assertGreater(len(resp.content), 0)

    @override_settings(
        GEMINI_API_KEY="test-gemini-key",
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        },
    )
    @patch("inventory.services.ai_service.genai.Client")
    def test_ai_service_reads_image_bytes_from_storage(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Vintage Seiko Automatic Diver Watch",
            description="• Automatic movement\n• Stainless steel case\n• Fully functional",
        )
        mock_client.models.generate_content.return_value = mock_response

        product = Product.objects.create(raw_note="1980s Seiko diver watch")
        ProductImage.objects.create(
            product=product,
            image=ContentFile(make_test_image_bytes(size=(80, 80), color="black", image_format="WEBP"), name="seiko.webp"),
            order=0,
        )

        result = generate_product_listing(product, language="en")
        self.assertEqual(result["title"], "Vintage Seiko Automatic Diver Watch")
        self.assertIn("Automatic movement", result["description"])

        # Verify generate_content received prompt string and image Part
        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        self.assertEqual(len(contents), 2)  # 1 prompt text + 1 image Part
