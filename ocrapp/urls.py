from django.urls import path

from .views import home_view, process_receipt_api_view, update_receipt_api_view


urlpatterns = [
    path("", home_view, name="home"),
    path("api/process-receipt/", process_receipt_api_view, name="process_receipt_api"),
    path("api/update-receipt/", update_receipt_api_view, name="update_receipt_api"),
]