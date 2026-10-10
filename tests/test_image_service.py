import io

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


class ImageServiceTests(TestCase):
    def create_test_image_file(self, filename="test.jpg", format="JPEG", size=(100, 100), color="blue"):
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format=format)
        buf.seek(0)
        return SimpleUploadedFile(filename, buf.getvalue(), content_type=f"image/{format.lower()}")

    def test_convert_jpeg_to_webp_success(self):
        uploaded = self.create_test_image_file(filename="vintage_jacket.jpg", format="JPEG")
        webp_file = process_and_convert_to_webp(uploaded)

        self.assertTrue(webp_file.name.endswith(".webp"))
        self.assertTrue(webp_file.name.startswith("vintage_jacket_"))

        # Verify output is a real WebP image readable by Pillow
        with Image.open(webp_file) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (100, 100))

    def test_convert_png_to_webp_preserves_dimensions(self):
        uploaded = self.create_test_image_file(filename="shoes.png", format="PNG", size=(300, 200), color="green")
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
