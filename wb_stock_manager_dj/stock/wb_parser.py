# stock/wb_simple_service.py
import requests
import json
from datetime import datetime, timedelta
import time
from django.core.cache import cache
from django.conf import settings

class WBSimpleService:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://statistics-api.wildberries.ru/api/v1/supplier"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_cache_key(self, user_id):
        """Генерируем ключ для кэша на основе пользователя"""
        return f"wb_today_data_{user_id}"
    
    def make_request_with_retry(self, endpoint, params, max_retries=3):
        """Делаем запрос с повторными попытками"""
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 5
                    print(f"⏳ 429 Too Many Requests. Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Ошибка при запросе {endpoint} (попытка {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2)
        
        return None
    
    def get_orders_today(self):
        """Получить заказы за сегодня"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = today.strftime("%Y-%m-%d")
        
        params = {"dateFrom": date_from, "flag": 1}
        return self.make_request_with_retry("orders", params)
    
    def get_sales_today(self):
        """Получить продажи за сегодня"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = today.strftime("%Y-%m-%d")
        
        params = {"dateFrom": date_from, "flag": 1}
        return self.make_request_with_retry("sales", params)
    
    def get_price_with_discount(self, item):
        """Получить правильную цену"""
        price_fields = ['priceWithDisc', 'finishedPrice', 'totalPrice', 'price']
        for field in price_fields:
            if field in item and item[field] is not None:
                price = float(item[field])
                return abs(price)
        return 0
    
    def get_article_name(self, item):
        """Получить название товара"""
        if 'subject' in item and item['subject']:
            name = item['subject']
            if 'brand' in item and item['brand']:
                name = f"{item['brand']} - {name}"
            return name
        elif 'techSize' in item and 'nmId' in item:
            return f"Арт. {item['nmId']} (разм. {item['techSize']})"
        elif 'nmId' in item:
            return f"Арт. {item['nmId']}"
        else:
            return "Неизвестный товар"
    
    def get_article_code(self, item):
        """Получить артикул"""
        return item.get('nmId', 'N/A')
    
    def filter_real_sales(self, sales):
        """Фильтрует реальные выкупы и возвраты"""
        real_sales = []
        returns = []
        
        for sale in sales:
            original_price = sale.get('priceWithDisc', 0) or sale.get('finishedPrice', 0) or sale.get('totalPrice', 0) or 0
            
            if original_price < 0:
                returns.append(sale)
            else:
                real_sales.append(sale)
        
        return real_sales, returns
    
    def find_cancellations_from_orders(self, orders, real_sales):
        """Находит отказы сравнивая заказы и выкупы - ИСПРАВЛЕННАЯ ЛОГИКА"""
        if not orders:
            return []
        
        # Собираем ID всех ВЫКУПЛЕННЫХ заказов
        sold_order_ids = set()
        for sale in real_sales:
            # Используем odid для сопоставления с заказами
            order_id = sale.get('odid')
            if order_id:
                sold_order_ids.add(str(order_id))
        
        print(f"🔍 Найдено выкупленных заказов: {len(sold_order_ids)}")
        print(f"🔍 Всего заказов: {len(orders)}")
        
        # Отказами считаем заказы, которых НЕТ в выкупах
        cancellations = []
        for order in orders:
            order_id = str(order.get('odid', ''))
            # Если заказ есть в orders, но нет в sold_order_ids - это отказ
            if order_id and order_id not in sold_order_ids:
                cancellations.append(order)
        
        print(f"🔍 Найдено отказов: {len(cancellations)}")
        
        # Дополнительная проверка: выводим первые несколько ID для отладки
        if orders and real_sales:
            sample_order_ids = [str(order.get('odid', '')) for order in orders[:3]]
            sample_sale_ids = [str(sale.get('odid', '')) for sale in real_sales[:3]]
            print(f"📋 Пример ID заказов: {sample_order_ids}")
            print(f"📋 Пример ID выкупов: {sample_sale_ids}")
        
        return cancellations
    
    def analyze_today_data(self, user_id):
        """Анализ данных только за сегодня с кэшированием"""
        cache_key = self.get_cache_key(user_id)
        
        # Пробуем получить данные из кэша
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"📦 Данные из кэша для пользователя {user_id}")
            return cached_data
        
        print(f"🔍 Загрузка данных за сегодня для пользователя {user_id}")
        
        try:
            # Получаем данные за сегодня
            orders = self.get_orders_today() or []
            all_sales = self.get_sales_today() or []
            
            print(f"📊 Получено за сегодня: {len(orders)} заказов, {len(all_sales)} продаж")
            
            # Фильтруем выкупы от возвратов
            real_sales, returns_from_sales = self.filter_real_sales(all_sales)
            all_returns = returns_from_sales
            
            print(f"📊 После фильтрации: {len(real_sales)} выкупов, {len(all_returns)} возвратов")
            
            # Находим отказы - ИСПРАВЛЕННАЯ ЛОГИКА
            cancellations = self.find_cancellations_from_orders(orders, real_sales)
            
            # Статистика
            total_orders = len(orders)
            total_sales = len(real_sales)
            total_cancellations = len(cancellations)
            total_returns = len(all_returns)
            
            # Суммы
            orders_sum = sum(self.get_price_with_discount(order) for order in orders)
            sales_sum = sum(self.get_price_with_discount(sale) for sale in real_sales)
            cancellations_sum = sum(self.get_price_with_discount(order) for order in cancellations)
            returns_sum = sum(self.get_price_with_discount(sale) for sale in all_returns)
            
            # Проценты
            conversion_rate = (total_sales / total_orders * 100) if total_orders > 0 else 0
            cancellation_rate = (total_cancellations / total_orders * 100) if total_orders > 0 else 0
            
            print(f"📈 Итоговая статистика:")
            print(f"   Заказы: {total_orders} на {orders_sum:.0f} руб.")
            print(f"   Выкупы: {total_sales} на {sales_sum:.0f} руб.")
            print(f"   Отказы: {total_cancellations} на {cancellations_sum:.0f} руб.")
            print(f"   Возвраты: {total_returns} на {returns_sum:.0f} руб.")
            print(f"   Конверсия: {conversion_rate:.1f}%")
            
            # Форматируем данные для отображения (только первые 8)
            def format_items_for_display(items, limit=8):
                formatted = []
                for item in items[:limit]:
                    formatted.append({
                        'id': item.get('odid') or item.get('srid', 'N/A'),
                        'article': self.get_article_code(item),
                        'name': self.get_article_name(item),
                        'price': self.get_price_with_discount(item),
                        'date': self.format_display_date(item.get('date', ''))
                    })
                return formatted
            
            result = {
                'date': datetime.now().strftime("%d.%m.%Y"),
                'orders': {
                    'count': total_orders,
                    'sum': orders_sum,
                    'data': format_items_for_display(orders)
                },
                'sales': {
                    'count': total_sales,
                    'sum': sales_sum,
                    'data': format_items_for_display(real_sales)
                },
                'cancellations': {
                    'count': total_cancellations,
                    'sum': cancellations_sum,
                    'data': format_items_for_display(cancellations)
                },
                'returns': {
                    'count': total_returns,
                    'sum': returns_sum,
                    'data': format_items_for_display(all_returns)
                },
                'conversion_rate': conversion_rate,
                'cancellation_rate': cancellation_rate,
                'success': True
            }
            
            # Сохраняем в кэш на 20 минут
            cache.set(cache_key, result, 60 * 20)
            print(f"💾 Сохранено в кэш на 20 минут")
            
            return result
            
        except Exception as e:
            print(f"❌ Ошибка анализа: {e}")
            error_result = {
                'success': False,
                'error': str(e),
                'date': datetime.now().strftime("%d.%m.%Y"),
                'orders': {'count': 0, 'sum': 0, 'data': []},
                'sales': {'count': 0, 'sum': 0, 'data': []},
                'cancellations': {'count': 0, 'sum': 0, 'data': []},
                'returns': {'count': 0, 'sum': 0, 'data': []},
                'conversion_rate': 0,
                'cancellation_rate': 0
            }
            # Даже ошибку кэшируем на 5 минут, чтобы не спамить API
            cache.set(cache_key, error_result, 60 * 5)
            return error_result
    
    def format_display_date(self, date_str):
        """Форматирование даты для отображения"""
        try:
            clean_date = date_str.replace('Z', '')
            date_obj = datetime.fromisoformat(clean_date)
            return date_obj.strftime("%H:%M")
        except:
            return date_str

def get_wb_simple_service(user):
    """Получить сервис для пользователя"""
    try:
        profile = user.profile
        api_token = profile.get_api_token()
        if api_token:
            return WBSimpleService(api_token)
    except Exception as e:
        print(f"❌ Ошибка получения сервиса: {e}")
    return None

def clear_wb_cache(user):
    """Очистить кэш для пользователя"""
    try:
        service = WBSimpleService("dummy")  # Просто для получения ключа
        cache_key = service.get_cache_key(user.id)
        cache.delete(cache_key)
        print(f"🧹 Кэш очищен для пользователя {user.id}")
    except Exception as e:
        print(f"❌ Ошибка очистки кэша: {e}")