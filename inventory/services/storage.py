from botocore.config import Config
from storages.backends.s3boto3 import S3Boto3Storage


class OCIObjectStorage(S3Boto3Storage):
    """
    Storage backend for Oracle Cloud Infrastructure (OCI) Object Storage
    using the Amazon S3-compatible API.

    OCI-specific configuration defaults:
    - default_acl = None: OCI does not support standard S3 x-amz-acl headers.
    - signature_version = 's3v4': OCI S3 compatibility requires AWS Signature Version 4.
    - addressing_style = 'path': OCI requires path-style access (endpoint/bucket/object).
    - querystring_auth = False: Generates direct public URLs when bucket/object is public.
    - file_overwrite = False: Appends unique suffix rather than overwriting existing items.
    - payload_signing_enabled = False: OCI S3 compatibility does not support AWS chunked encoding payload signing.
    """
    default_acl = None
    signature_version = "s3v4"
    addressing_style = "path"
    file_overwrite = False
    querystring_auth = False

    def __init__(self, **settings):
        super().__init__(**settings)
        self.client_config = Config(
            s3={
                "addressing_style": self.addressing_style,
                "payload_signing_enabled": False,
            },
            signature_version=self.signature_version,
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            proxies=self.proxies,
        )
