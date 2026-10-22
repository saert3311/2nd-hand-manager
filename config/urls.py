"""
URL configuration for config project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from inventory.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('storefront.urls')),
    path('', include('inventory.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
