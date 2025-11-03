from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Product


def product_stock_history(request, product_id):
    """API endpoint для получения истории остатков товара"""
    product = get_object_or_404(Product, id=product_id)
    history_data = product.get_stock_history()
    
    return JsonResponse(history_data)
