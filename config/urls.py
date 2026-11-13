"""
URL configuration for config project.
"""

import mimetypes
import posixpath

from django.conf import settings
from django.conf.urls.static import static
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.urls import include, path, re_path

from inventory.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('storefront.urls')),
    path('', include('inventory.urls')),
]


def _serve_testing_media(request, path):
    """Serve media files from default_storage during automated browser tests."""
    normalized = posixpath.normpath(path).lstrip('/')
    if not normalized or normalized == '.' or normalized.startswith('..'):
        raise Http404('Invalid media path')
    try:
        if not default_storage.exists(normalized):
            raise Http404('Media file not found')
        file_obj = default_storage.open(normalized, 'rb')
    except (SuspiciousFileOperation, FileNotFoundError) as exc:
        raise Http404('Media file not found') from exc

    content_type, _ = mimetypes.guess_type(normalized)
    return FileResponse(file_obj, content_type=content_type or 'application/octet-stream')


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.IS_TESTING:
    media_prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        re_path(rf'^{media_prefix}(?P<path>.*)$', _serve_testing_media),
    ]
