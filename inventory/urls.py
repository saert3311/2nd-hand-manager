from django.urls import path

from .views import (
    CustomLoginView,
    CustomLogoutView,
    dashboard_view,
    generate_ai_view,
    product_detail_view,
    product_download_zip_view,
    product_intake_view,
    root_redirect_view,
)

app_name = "inventory"

urlpatterns = [
    path("", root_redirect_view, name="root"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("intake/", product_intake_view, name="intake"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("products/<int:pk>/", product_detail_view, name="product_detail"),
    path("products/<int:pk>/download-zip/", product_download_zip_view, name="download_zip"),
    path("products/<int:pk>/generate-ai/", generate_ai_view, name="generate_ai"),
]

