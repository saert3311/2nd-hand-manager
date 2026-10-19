from django.urls import path

from .views import (
    CustomLoginView,
    CustomLogoutView,
    dashboard_view,
    generate_ai_view,
    intake_identify_view,
    manifest_view,
    product_add_clarification_view,
    product_answer_clarification_view,
    product_delete_clarification_view,
    product_detail_view,
    product_download_zip_view,
    product_intake_view,
    product_manage_link_view,
    push_subscribe_view,
    push_test_view,
    push_unsubscribe_view,
    root_redirect_view,
    service_worker_view,
)

app_name = "inventory"

urlpatterns = [
    path("", root_redirect_view, name="root"),
    path("manifest.json", manifest_view, name="manifest"),
    path("sw.js", service_worker_view, name="service_worker"),
    path("api/push/subscribe/", push_subscribe_view, name="push_subscribe"),
    path("api/push/unsubscribe/", push_unsubscribe_view, name="push_unsubscribe"),
    path("api/push/test/", push_test_view, name="push_test"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("intake/", product_intake_view, name="intake"),
    path("intake/identify/", intake_identify_view, name="intake_identify"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("products/<int:pk>/", product_detail_view, name="product_detail"),
    path("products/<int:pk>/download-zip/", product_download_zip_view, name="download_zip"),
    path("products/<int:pk>/generate-ai/", generate_ai_view, name="generate_ai"),
    path("products/<int:pk>/links/", product_manage_link_view, name="manage_link"),
    path("products/<int:pk>/clarifications/add/", product_add_clarification_view, name="add_clarification"),
    path("products/<int:pk>/clarifications/<int:clarification_pk>/answer/", product_answer_clarification_view, name="answer_clarification"),
    path("products/<int:pk>/clarifications/<int:clarification_pk>/delete/", product_delete_clarification_view, name="delete_clarification"),
]

