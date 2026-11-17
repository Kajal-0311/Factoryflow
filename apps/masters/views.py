from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.decorators import role_required
from apps.masters.models import (
    Product, Customer, Supplier, RawMaterial, PackagingMaterial, Category, UnitOfMeasurement
)

@login_required
def product_list(request):
    products = Product.objects.select_related('category', 'uom').all()
    customers = Customer.objects.all()
    suppliers = Supplier.objects.all()
    raw_materials = RawMaterial.objects.select_related('uom').all()
    packaging_materials = PackagingMaterial.objects.select_related('uom').all()

    context = {
        'products': products,
        'customers': customers,
        'suppliers': suppliers,
        'raw_materials': raw_materials,
        'packaging_materials': packaging_materials,
        'active_tab': request.GET.get('tab', 'products'),
    }
    return render(request, 'masters/catalog.html', context)
