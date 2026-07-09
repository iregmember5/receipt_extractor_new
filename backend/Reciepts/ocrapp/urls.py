from django.urls import path

from .views import home_view, process_receipt_api_view, process_receipt_json_view, compare_crop_view


urlpatterns = [
    path("", home_view, name="home"),
    path("api/process-receipt/", process_receipt_api_view, name="process_receipt_api"),
    path("api/process-receipt-json/", process_receipt_json_view, name="process_receipt_json"),
    path("api/compare-crop/", compare_crop_view, name="compare_crop"),
]
