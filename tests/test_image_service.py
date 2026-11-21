from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from inventory.services.image_service import (
    MAX_IMAGE_SIZE_BYTES,
    process_and_convert_to_webp,
    validate_image_file,
    validate_images_count,
)
from tests.helpers import make_test_image_file


class ImageServiceTests(TestCase):
    def test_convert_jpeg_to_webp_success(self):
        uploaded = make_test_image_file(name="vintage_jacket.jpg", size=(100, 100), color="blue", image_format="JPEG")
        webp_file = process_and_convert_to_webp(uploaded)

        self.assertTrue(webp_file.name.endswith(".webp"))
        self.assertTrue(webp_file.name.startswith("vintage_jacket_"))

        # Verify output is a real WebP image readable by Pillow
        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (100, 100))

    def test_convert_png_to_webp_preserves_dimensions(self):
        uploaded = make_test_image_file(
            name="shoes.png",
            size=(300, 200),
            color="green",
            image_format="PNG",
            content_type="image/png",
        )
        webp_file = process_and_convert_to_webp(uploaded)

        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (300, 200))

    def test_exceeds_size_limit_raises_validation_error(self):
        # Create dummy file > 10MB
        oversized = SimpleUploadedFile(
            "large_file.jpg",
            b"0" * (MAX_IMAGE_SIZE_BYTES + 1024),
            content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError):
            validate_image_file(oversized)

    def test_corrupt_image_raises_validation_error(self):
        corrupt = SimpleUploadedFile(
            "fake.jpg",
            b"this is not a valid image stream",
            content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError):
            validate_image_file(corrupt)

    def test_validate_images_count(self):
        valid_list = [f"file{i}.jpg" for i in range(10)]
        validate_images_count(valid_list)  # Should not raise

        invalid_list = [f"file{i}.jpg" for i in range(11)]
        with self.assertRaises(ValidationError):
            validate_images_count(invalid_list)

    def test_downscales_images_exceeding_2560px(self):
        uploaded = make_test_image_file(name="huge_landscape.jpg", size=(3000, 1500), color="blue", image_format="JPEG")
        webp_file = process_and_convert_to_webp(uploaded)

        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (2560, 1280))

    def test_supports_high_megapixels_mobile_camera_without_bomb_error(self):
        # 30 Megapixels image (6000 x 5000) simulates modern 48MP/50MP smartphone camera output
        # Previously failed when Image.MAX_IMAGE_PIXELS was 25_000_000
        uploaded = make_test_image_file(name="phone_camera_50mp.jpg", size=(6000, 5000), color="blue", image_format="JPEG")
        validate_image_file(uploaded)
        webp_file = process_and_convert_to_webp(uploaded)

        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size[0], 2560)
            self.assertEqual(img.size[1], round(5000 * 2560 / 6000))

    def test_convert_webp_input_to_webp_output_success(self):
        uploaded = make_test_image_file(
            name="client_compressed.webp",
            size=(800, 600),
            color="blue",
            image_format="WEBP",
            content_type="image/webp",
        )
        webp_file = process_and_convert_to_webp(uploaded)

        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (800, 600))
