from django.urls import path

from .views import (
    catalog_view,
    category_catalog_view,
    cookies_policy_view,
    go_marketplace_link_view,
    go_store_whatsapp_view,
    go_whatsapp_view,
    home_view,
    how_to_buy_view,
    legacy_product_detail_redirect_view,
    legal_notice_view,
    privacy_policy_view,
    public_product_detail_view,
    robots_view,
    sitemap_view,
)

app_name = "storefront"

urlpatterns = [
    path("", home_view, name="home"),
    path("tienda/", catalog_view, name="catalog"),
    path("tienda/categoria/<slug:category_slug>/", category_catalog_view, name="category"),
    path("tienda/producto/<slug:slug>-<int:pk>/", public_product_detail_view, name="product_detail"),
    path("p/<slug:slug>-<int:pk>/", legacy_product_detail_redirect_view, name="legacy_product_detail"),
    path("como-comprar/", how_to_buy_view, name="how_to_buy"),
    path("go/whatsapp/<int:pk>/", go_whatsapp_view, name="go_whatsapp_product"),
    path("go/whatsapp/<int:pk>/", go_whatsapp_view, name="go_whatsapp"),
    path("go/whatsapp/", go_store_whatsapp_view, name="go_whatsapp"),
    path("go/whatsapp/", go_store_whatsapp_view, name="go_whatsapp_store"),
    path("go/link/<int:link_pk>/", go_marketplace_link_view, name="go_listing"),
    path("go/link/<int:link_pk>/", go_marketplace_link_view, name="go_marketplace_link"),
    path("aviso-legal/", legal_notice_view, name="legal_notice"),
    path("privacidad/", privacy_policy_view, name="privacy"),
    path("privacidad/", privacy_policy_view, name="privacy_policy"),
    path("cookies/", cookies_policy_view, name="cookies"),
    path("cookies/", cookies_policy_view, name="cookies_policy"),
    path("legal/aviso-legal/", legal_notice_view, name="legacy_legal_notice"),
    path("legal/privacidad/", privacy_policy_view, name="legacy_privacy_policy"),
    path("legal/cookies/", cookies_policy_view, name="legacy_cookies_policy"),
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path("robots.txt", robots_view, name="robots"),
]
