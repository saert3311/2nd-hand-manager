import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def generate_vapid_keypair() -> tuple[str, str]:
    """
    Generates an ECDSA P-256 (prime256v1 / secp256r1) keypair encoded in
    URL-safe Base64 without padding, suitable for Web Push VAPID (RFC 8292).
    Returns (public_key, private_key).
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, byteorder="big")
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    vapid_public = base64.urlsafe_b64encode(public_bytes).decode("ascii").rstrip("=")
    vapid_private = base64.urlsafe_b64encode(private_bytes).decode("ascii").rstrip("=")
    return vapid_public, vapid_private


class Command(BaseCommand):
    help = "Generate a fresh ECDSA P-256 VAPID keypair for Web Push Notifications (.env format)."

    def handle(self, *args, **options):
        public_key, private_key = generate_vapid_keypair()
        self.stdout.write(self.style.SUCCESS("# Add the following VAPID keys to your .env file:"))
        self.stdout.write(f"VAPID_PUBLIC_KEY={public_key}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={private_key}")
        self.stdout.write("VAPID_CLAIMS_EMAIL=mailto:admin@yourdomain.com")
