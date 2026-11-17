from django.urls import path
from apps.sales import views

app_name = 'sales'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('new/', views.create_order, name='create_order'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/approve/', views.approve_order, name='approve_order'),
    path('<int:pk>/reject/', views.reject_order, name='reject_order'),
    path('<int:pk>/invoice/', views.create_invoice_from_order, name='create_invoice'),
    path('<int:pk>/dispatch/', views.record_dispatch, name='record_dispatch'),
    path('api/price/', views.api_get_product_price, name='api_price'),
]
