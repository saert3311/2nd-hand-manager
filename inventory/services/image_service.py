import io
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGES_PER_PRODUCT = 10
DEFAULT_WEBP_QUALITY = 82
MAX_DIMENSION = 2048
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "TIFF", "BMP", "MPO"}

# Protect against decompression bomb (pixel flood) DoS attacks
Image.MAX_IMAGE_PIXELS = 25_000_000


def validate_image_file(uploaded_file):
    """
    Validates that the uploaded file is within the 10MB limit and is a readable image.
    Verifies MIME/format against allowed image formats and prevents decompression bombs.
    """
    if uploaded_file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            _("Image '%(filename)s' exceeds the 10MB limit (%(size).1fMB).")
            % {"filename": uploaded_file.name, "size": uploaded_file.size / (1024 * 1024)}
        )

    # Verify that Pillow can read the image header and format
    try:
        current_pos = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
        img = Image.open(uploaded_file)
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                _("Image format '%(format)s' is not supported. Please upload JPEG, PNG, or WebP.")
                % {"format": fmt or "unknown"}
            )
        img.verify()
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(current_pos)
    except Image.DecompressionBombError as dbe:
        raise ValidationError(
            _("File '%(filename)s' is too large in pixel dimensions (possible decompression bomb).")
            % {"filename": uploaded_file.name}
        ) from dbe
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            _("File '%(filename)s' is not a valid or readable image.")
            % {"filename": uploaded_file.name}
        ) from exc


def validate_images_count(images_list):
    """
    Validates that the total number of images does not exceed 10.
    """
    if len(images_list) > MAX_IMAGES_PER_PRODUCT:
        raise ValidationError(
            _("You can upload a maximum of %(max)d images per product. Received %(count)d.")
            % {"max": MAX_IMAGES_PER_PRODUCT, "count": len(images_list)}
        )



def process_and_convert_to_webp(uploaded_file, quality=DEFAULT_WEBP_QUALITY, max_dimension=MAX_DIMENSION) -> ContentFile:
    """
    Processes an uploaded image:
    1. Reads image into Pillow.
    2. Corrects orientation based on EXIF transpose.
    3. Resizes down if larger than max_dimension while maintaining aspect ratio.
    4. Converts to WebP format.
    5. Returns a Django ContentFile with a .webp filename.
    """
    validate_image_file(uploaded_file)

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    with Image.open(uploaded_file) as img:
        # Correct mobile camera orientation
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass  # Fall back if no EXIF or transpose error

        # Ensure color mode is compatible with WebP (RGB or RGBA)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Downscale if image is excessively large
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Save to in-memory WebP buffer
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=4)
        buffer.seek(0)

        # Derive clean .webp filename
        original_stem = Path(uploaded_file.name).stem if hasattr(uploaded_file, "name") and uploaded_file.name else "img"
        clean_stem = "".join(c for c in original_stem if c.isalnum() or c in ("-", "_"))[:30]
        if not clean_stem:
            clean_stem = "img"
        webp_filename = f"{clean_stem}_{uuid.uuid4().hex[:8]}.webp"

        return ContentFile(buffer.getvalue(), name=webp_filename)
