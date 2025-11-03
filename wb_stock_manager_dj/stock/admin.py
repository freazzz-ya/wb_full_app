from django.contrib import admin
from .models import Product, StockMovement

class StockMovementInline(admin.TabularInline):
    """Движения товара прямо в карточке товара"""
    model = StockMovement
    extra = 1
    fields = ('movement_type', 'quantity', 'date', 'notes')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'article', 'purchase_date', 'initial_quantity', 'current_stock_display', 'days_in_stock_display', 'created_at')
    list_filter = ('purchase_date', 'created_at')
    search_fields = ('name', 'article')
    inlines = [StockMovementInline]
    
    # Поля в форме редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'article', 'image')
        }),
        ('Закупка', {
            'fields': ('purchase_date', 'initial_quantity')
        }),
    )
    
    def current_stock_display(self, obj):
        return obj.current_stock
    current_stock_display.short_description = 'Текущий остаток'
    
    def days_in_stock_display(self, obj):
        return f"{obj.days_in_stock} дней"
    days_in_stock_display.short_description = 'Дней на складе'

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type_display', 'quantity', 'date', 'created_at')
    list_filter = ('movement_type', 'date')
    search_fields = ('product__name', 'product__article')
    
    def movement_type_display(self, obj):
        return obj.get_movement_type_display()
    movement_type_display.short_description = 'Тип операции'