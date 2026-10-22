from django.urls import path

from .views import (
    catalog_view,
    cookies_policy_view,
    go_marketplace_link_view,
    go_whatsapp_view,
    legal_notice_view,
    privacy_policy_view,
    public_product_detail_view,
    robots_view,
    sitemap_view,
)

app_name = "storefront"

urlpatterns = [
    path("", catalog_view, name="catalog"),
    path("p/<slug:slug>-<int:pk>/", public_product_detail_view, name="product_detail"),
    path("go/whatsapp/<int:pk>/", go_whatsapp_view, name="go_whatsapp"),
    path("go/link/<int:link_pk>/", go_marketplace_link_view, name="go_marketplace_link"),
    path("legal/aviso-legal/", legal_notice_view, name="legal_notice"),
    path("legal/privacidad/", privacy_policy_view, name="privacy_policy"),
    path("legal/cookies/", cookies_policy_view, name="cookies_policy"),
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path("robots.txt", robots_view, name="robots"),
]
