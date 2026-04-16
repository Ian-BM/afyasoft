from django.urls import path

from . import views

urlpatterns = [
    path("sw.js", views.service_worker, name="service_worker"),
    path("api/sync-sale/", views.sync_sale, name="sync_sale"),
    path("", views.dashboard, name="dashboard"),
    path("sales/", views.sales_pos, name="sales"),
    path("sales/receipt/<int:pk>/", views.receipt, name="receipt"),
    path("receipts/", views.receipt_archive, name="receipt_archive"),
    path("receipts/<str:receipt_number>/", views.receipt_by_number, name="receipt_by_number"),
    path("inventory/", views.inventory_list, name="inventory"),
    path("inventory/add/", views.medicine_add, name="medicine_add"),
    path("inventory/<int:pk>/edit/", views.medicine_edit, name="medicine_edit"),
    path("inventory/<int:pk>/delete/", views.medicine_delete, name="medicine_delete"),
    path("inventory/<int:pk>/adjust/", views.stock_adjust, name="stock_adjust"),
    path("inventory/<int:pk>/expire/", views.stock_expire, name="stock_expire"),
    path("restock/", views.restock, name="restock"),
    path("expiry/", views.expiry_list, name="expiry"),
    path("reports/", views.reports, name="reports"),
    path("reports/stock-movements/", views.stock_movements, name="stock_movements"),
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/add/", views.staff_add, name="staff_add"),
    path("staff/<int:user_id>/status/", views.staff_toggle_active, name="staff_toggle_active"),
    path("subscription/renew/", views.subscription_renew, name="subscription_renew"),
]
