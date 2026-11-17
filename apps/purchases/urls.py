from django.urls import path
from apps.purchases import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='purchase_list'),
    path('new/', views.create_purchase, name='create_purchase'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('<int:pk>/confirm/', views.confirm_purchase, name='confirm_purchase'),
]
