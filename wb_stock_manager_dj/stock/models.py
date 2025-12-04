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


class AdvertisingCampaign(models.Model):
    """Рекламная кампания Wildberries"""
    CAMPAIGN_TYPES = (
        ('search', '🔍 Поисковая кампания'),
        ('auction', '⚡ Аукцион'),
    )
    
    STATUS_CHOICES = (
        ('active', '🟢 Активная'),
        ('paused', '🟡 На паузе'),
        ('completed', '🔴 Завершена'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ad_campaigns')
    name = models.CharField(max_length=255, verbose_name="Название кампании")
    campaign_type = models.CharField(max_length=10, choices=CAMPAIGN_TYPES, verbose_name="Тип кампании")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name="Статус")
    
    # Убрали daily_budget и bid, так как будем вводить статистику вручную
    
    # Товары в кампании
    products = models.ManyToManyField('Product', related_name='ad_campaigns', verbose_name="Товары")
    
    # Даты
    start_date = models.DateField(default=timezone.now, verbose_name="Дата начала")
    end_date = models.DateField(blank=True, null=True, verbose_name="Дата окончания")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Рекламная кампания"
        verbose_name_plural = "Рекламные кампании"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"

    @property
    def days_running(self):
        """Сколько дней работает кампания"""
        from datetime import date
        end_date = self.end_date or date.today()
        return (end_date - self.start_date).days

    @property
    def total_spent(self):
        """Общие затраты на кампанию"""
        return self.daily_stats.aggregate(total=models.Sum('spent'))['total'] or 0

    @property
    def total_views(self):
        """Общее количество показов"""
        return self.daily_stats.aggregate(total=models.Sum('views'))['total'] or 0

    @property
    def total_clicks(self):
        """Общее количество кликов"""
        return self.daily_stats.aggregate(total=models.Sum('clicks'))['total'] or 0

    @property
    def total_cart_adds(self):
        """Общее количество добавлений в корзину"""
        return self.daily_stats.aggregate(total=models.Sum('cart_adds'))['total'] or 0

    @property
    def total_orders(self):
        """Общее количество заказов"""
        return self.daily_stats.aggregate(total=models.Sum('orders'))['total'] or 0

    @property
    def ctr(self):
        """CTR (Click-Through Rate)"""
        if self.total_views > 0:
            return (self.total_clicks / self.total_views) * 100
        return 0

    @property
    def cpc(self):
        """Средняя стоимость клика"""
        if self.total_clicks > 0:
            return self.total_spent / self.total_clicks
        return 0

    @property
    def cpo(self):
        """Средняя стоимость заказа"""
        if self.total_orders > 0:
            return self.total_spent / self.total_orders
        return 0

    @property
    def conversion_rate(self):
        """Конверсия из клика в заказ"""
        if self.total_clicks > 0:
            return (self.total_orders / self.total_clicks) * 100
        return 0

    @property
    def cart_conversion_rate(self):
        """Конверсия из корзины в заказ"""
        if self.total_cart_adds > 0:
            return (self.total_orders / self.total_cart_adds) * 100
        return 0

    @property
    def is_active(self):
        """Активна ли кампания"""
        from datetime import date
        if self.status != 'active':
            return False
        if self.end_date and self.end_date < date.today():
            return False
        return True


class CampaignDailyStats(models.Model):
    """Ежедневная статистика по рекламной кампании"""
    campaign = models.ForeignKey(AdvertisingCampaign, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField(verbose_name="Дата")
    
    # Основные метрики
    views = models.PositiveIntegerField(default=0, verbose_name="Показы")
    clicks = models.PositiveIntegerField(default=0, verbose_name="Клики")
    cart_adds = models.PositiveIntegerField(default=0, verbose_name="Добавления в корзину")
    orders = models.PositiveIntegerField(default=0, verbose_name="Заказы")
    spent = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Затраты (руб)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Статистика кампании"
        verbose_name_plural = "Статистика кампаний"
        ordering = ['-date']
        unique_together = ['campaign', 'date']

    def __str__(self):
        return f"{self.campaign.name} - {self.date}"

    @property
    def ctr(self):
        """CTR (Click-Through Rate)"""
        if self.views > 0:
            return (self.clicks / self.views) * 100
        return 0

    @property
    def cpc(self):
        """Стоимость клика"""
        if self.clicks > 0:
            return self.spent / self.clicks
        return 0

    @property
    def cpo(self):
        """Стоимость заказа"""
        if self.orders > 0:
            return self.spent / self.orders
        return 0

    @property
    def conversion_rate(self):
        """Конверсия из клика в заказ"""
        if self.clicks > 0:
            return (self.orders / self.clicks) * 100
        return 0


class CampaignGoal(models.Model):
    """Цели для рекламных кампаний"""
    GOAL_TYPES = (
        ('sales', '🎯 Увеличение продаж'),
        ('traffic', '🚀 Улучшение рекламы'),
        ('conversion', '📈 Повышение конверсии'),
        ('brand', '🏆 Укрепление бренда'),
        ('profit', '💰 Увеличение прибыли'),
        ('other', '📝 Другая цель'),
    )
    
    STATUS_CHOICES = (
        ('active', '🟢 Активная'),
        ('completed', '✅ Завершена'),
        ('archived', '📁 В архиве'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaign_goals')
    title = models.CharField(max_length=255, verbose_name="Название цели")
    goal_type = models.CharField(max_length=15, choices=GOAL_TYPES, verbose_name="Тип цели")
    description = models.TextField(verbose_name="Описание цели", blank=True)
    
    # Прогресс цели
    target_value = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Целевое значение", null=True, blank=True)
    current_value = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Текущее значение")
    progress_percentage = models.PositiveIntegerField(default=0, verbose_name="Прогресс (%)")
    
    # Связанные кампании
    campaigns = models.ManyToManyField('AdvertisingCampaign', related_name='goals', blank=True, verbose_name="Связанные кампании")
    
    # Даты
    start_date = models.DateField(default=timezone.now, verbose_name="Дата начала")
    deadline = models.DateField(null=True, blank=True, verbose_name="Дедлайн")
    completed_date = models.DateField(null=True, blank=True, verbose_name="Дата завершения")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name="Статус")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Цель кампании"
        verbose_name_plural = "Цели кампаний"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_goal_type_display()})"

    def save(self, *args, **kwargs):
        """Автоматически рассчитываем прогресс при сохранении"""
        if self.target_value and self.target_value > 0:
            self.progress_percentage = min(100, int((self.current_value / self.target_value) * 100))
        else:
            self.progress_percentage = 0
            
        # Если прогресс 100% и цель активна - помечаем как завершенную
        if self.progress_percentage >= 100 and self.status == 'active':
            self.status = 'completed'
            self.completed_date = timezone.now().date()
            
        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        """Осталось дней до дедлайна"""
        from datetime import date
        if self.deadline and self.status == 'active':
            remaining = (self.deadline - date.today()).days
            return max(0, remaining)
        return None

    @property
    def is_overdue(self):
        """Просрочена ли цель"""
        from datetime import date
        if self.deadline and self.status == 'active' and self.deadline < date.today():
            return True
        return False


class GoalNote(models.Model):
    """Заметки к целям"""
    goal = models.ForeignKey(CampaignGoal, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=255, verbose_name="Заголовок заметки")
    content = models.TextField(verbose_name="Содержание заметки")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Заметка цели"
        verbose_name_plural = "Заметки целей"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.goal.title}"


class ProductKeyword(models.Model):
    """Ключевое слово для товара"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='keywords'
    )
    keyword = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['product', 'keyword']

    def __str__(self):
        return f"{self.keyword} - {self.product.name}"

    @property
    def current_position(self):
        latest = self.positions.order_by('-created_at').first()  # Изменено с '-date' на '-created_at'
        return latest.position if latest else None

    @property
    def last_checked(self):
        latest = self.positions.order_by('-created_at').first()  # Изменено с '-date' на '-created_at'
        return latest.created_at if latest else None


class ProductPosition(models.Model):
    """Позиция товара по ключевому слову"""
    keyword = models.ForeignKey(
        ProductKeyword, 
        on_delete=models.CASCADE, 
        related_name='positions'
    )
    position = models.IntegerField()  # 0 = не найден
    created_at = models.DateTimeField(auto_now_add=True)  # Автоматическая дата
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.keyword.keyword}: {self.position} ({self.created_at.date()})"
    
    @property
    def date(self):  # Свойство для обратной совместимости
        return self.created_at.date()