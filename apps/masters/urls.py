from django.urls import path
from apps.masters import views

app_name = 'masters'

urlpatterns = [
    path('', views.product_list, name='product_list'),
]
