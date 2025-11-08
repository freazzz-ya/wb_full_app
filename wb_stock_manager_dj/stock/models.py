from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
from datetime import date

# Функции для шифрования/дешифрования
def encrypt_token(token):
    """Шифруем API токен"""
    key = settings.ENCRYPTION_KEY
    f = Fernet(key)
    return f.encrypt(token.encode())

def decrypt_token(encrypted_token):
    """Расшифровываем API токен"""
    key = settings.ENCRYPTION_KEY
    f = Fernet(key)
    return f.decrypt(encrypted_token).decode()

class UserProfile(models.Model):
    """Профиль пользователя с API токеном"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    wb_api_token = models.BinaryField(blank=True, null=True, verbose_name="API токен Wildberries")
    wb_api_token_encrypted = models.BooleanField(default=False, verbose_name="Токен зашифрован")
    
    # Дополнительная информация
    company_name = models.CharField(max_length=255, blank=True, verbose_name="Название компании")
    contact_email = models.EmailField(blank=True, verbose_name="Контактный email")
    notification_enabled = models.BooleanField(default=True, verbose_name="Уведомления включены")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль {self.user.username}"

    def set_api_token(self, token):
        """Шифруем и сохраняем API токен только если передан новый токен"""
        if token and token.strip():  # Проверяем что токен не пустой
            # Если токен уже существует и совпадает с текущим - не делаем ничего
            current_token = self.get_api_token()
            if current_token and current_token == token.strip():
                return
                
            encrypted_token = encrypt_token(token.strip())
            self.wb_api_token = encrypted_token
            self.wb_api_token_encrypted = True
            self.save()

    def get_api_token(self):
        """Получаем и расшифровываем API токен"""
        if self.wb_api_token and self.wb_api_token_encrypted:
            try:
                return decrypt_token(self.wb_api_token)
            except:
                return None
        return None

    def has_api_token(self):
        """Проверяем, установлен ли API токен"""
        return bool(self.wb_api_token and self.wb_api_token_encrypted)
    

class Product(models.Model):
    """Модель товара с привязкой к пользователю"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255, verbose_name="Название товара")
    article = models.CharField(max_length=100, verbose_name="Артикул WB")
    initial_quantity = models.PositiveIntegerField(default=0, verbose_name="Первоначальная закупка")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото товара")
    
    # Новое поле - дата закупки товара
    purchase_date = models.DateField(
        default=timezone.now, 
        verbose_name="Дата закупки товара"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления в систему")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-purchase_date', '-created_at']
        unique_together = ['user', 'article']  # Артикул уникален в рамках пользователя

    def __str__(self):
        return f"{self.name} ({self.article})"

    @property
    def total_incoming(self):
        """Общее количество дозаказов"""
        from django.db.models import Sum
        return self.movements.filter(movement_type='in').aggregate(
            total=Sum('quantity')
        )['total'] or 0

    @property
    def total_outgoing(self):
        """Общее количество продаж"""
        from django.db.models import Sum
        return self.movements.filter(movement_type='out').aggregate(
            total=Sum('quantity')
        )['total'] or 0

    @property
    def current_stock(self):
        """Текущий остаток на складе"""
        return self.initial_quantity + self.total_incoming - self.total_outgoing

    @property
    def days_in_stock(self):
        """Сколько дней товар на складе"""
        from datetime import date
        return (date.today() - self.purchase_date).days

    def get_stock_history(self):
        """Возвращает историю остатков по дням"""
        from django.db.models import Sum
        from collections import OrderedDict
        from datetime import date, timedelta
        
        # Получаем все движения товара, отсортированные по дате
        movements = self.movements.all().order_by('date')
        
        # Если нет движений, возвращаем базовую историю
        if not movements:
            return {
                'dates': [self.purchase_date.strftime('%Y-%m-%d'), date.today().strftime('%Y-%m-%d')],
                'stocks': [self.initial_quantity, self.initial_quantity]
            }
        
        # Находим диапазон дат от закупки до сегодня
        start_date = self.purchase_date
        end_date = date.today()
        
        # Создаем словарь для хранения остатков по дням
        stock_history = OrderedDict()
        current_stock = self.initial_quantity
        
        # Добавляем начальную точку
        stock_history[start_date] = current_stock
        
        # Обрабатываем все движения
        for movement in movements:
            if movement.movement_type == 'in':
                current_stock += movement.quantity
            else:  # 'out'
                current_stock -= movement.quantity
            
            stock_history[movement.date] = current_stock
        
        # Добавляем сегодняшнюю дату если ее нет
        if end_date not in stock_history:
            stock_history[end_date] = current_stock
        
        # Преобразуем в списки для Chart.js
        dates = [d.strftime('%Y-%m-%d') for d in stock_history.keys()]
        stocks = list(stock_history.values())
        
        return {
            'dates': dates,
            'stocks': stocks
        }

    def get_stock_history_json(self):
        """Возвращает историю в JSON формате"""
        import json
        history = self.get_stock_history()
        return json.dumps(history)

class StockMovement(models.Model):
    """Модель движения товара"""
    MOVEMENT_TYPES = (
        ('in', '🟢 Приход (Дозаказ)'),
        ('out', '🔴 Расход (Продажа)'),
    )

    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='movements',
        verbose_name="Товар"
    )
    movement_type = models.CharField(
        max_length=3, 
        choices=MOVEMENT_TYPES, 
        verbose_name="Тип операции"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    date = models.DateField(verbose_name="Дата операции")
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Движение товара"
        verbose_name_plural = "Движения товаров"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.get_movement_type_display()} - {self.quantity}"
