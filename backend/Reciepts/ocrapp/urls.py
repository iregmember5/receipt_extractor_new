from django.urls import path

from .views import home_view, process_receipt_api_view, process_receipt_json_view, update_ocr_view


urlpatterns = [
    path("", home_view, name="home"),
    path("api/process-receipt/", process_receipt_api_view, name="process_receipt_api"),
    path("api/process-receipt-json/", process_receipt_json_view, name="process_receipt_json"),
    path("api/update-ocr/", update_ocr_view, name="update_ocr"),
]
