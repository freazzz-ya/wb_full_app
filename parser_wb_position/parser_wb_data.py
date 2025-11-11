import requests
import json
from datetime import datetime, timedelta
import os
from pathlib import Path

class WBAnalyticsParser:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://statistics-api.wildberries.ru/api/v1/supplier"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_orders(self, date_from):
        """
        Получить заказы с указанной даты
        """
        url = f"{self.base_url}/orders"
        params = {
            "dateFrom": date_from,
            "flag": 1
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении заказов: {e}")
            return None
    
    def get_sales(self, date_from):
        """
        Получить продажи (выкупы) с указанной даты
        """
        url = f"{self.base_url}/sales"
        params = {
            "dateFrom": date_from,
            "flag": 1
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении продаж: {e}")
            return None
    
    def get_returns(self, date_from):
        """
        Получить возвраты с указанной даты
        """
        url = f"{self.base_url}/returns"
        params = {
            "dateFrom": date_from,
            "flag": 1
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении возвратов: {e}")
            return None

    def get_cancellations(self, date_from):
        """
        Получить отказы через API стоков
        """
        url = f"{self.base_url}/stocks"
        params = {
            "dateFrom": date_from
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении стоков (для отказов): {e}")
            return None
    
    def get_price_with_discount(self, item):
        """
        Получить цену с учетом скидки (priceWithDisc)
        """
        # Пробуем разные варианты названия поля
        if 'priceWithDisc' in item:
            return item['priceWithDisc']
        elif 'finishedPrice' in item:
            return item['finishedPrice']
        elif 'totalPrice' in item:
            return item['totalPrice']
        else:
            return 0
    
    def format_date(self, date_str):
        """
        Форматирование даты для читаемого вывода
        """
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return date_str
    
    def filter_real_sales(self, sales):
        """
        Фильтрует реальные выкупы (исключает возвраты)
        """
        real_sales = []
        returns = []
        
        for sale in sales:
            price = self.get_price_with_discount(sale)
            # Если цена отрицательная - это возврат
            if price < 0:
                returns.append(sale)
            else:
                real_sales.append(sale)
        
        return real_sales, returns
    
    def find_cancellations_from_orders(self, orders, real_sales):
        """
        Находит отказы сравнивая заказы и выкупы
        """
        if not orders:
            return []
        
        # Собираем ID всех выкупленных заказов
        sold_order_ids = set()
        for sale in real_sales:
            order_id = sale.get('odid')
            if order_id:
                sold_order_ids.add(str(order_id))
        
        # Находим заказы, которых нет в выкупах - это отказы
        cancellations = []
        for order in orders:
            order_id = str(order.get('odid', ''))
            # Если заказ есть в заказах, но нет в выкупах - это отказ
            if order_id and order_id not in sold_order_ids:
                cancellations.append(order)
        
        return cancellations
    
    def analyze_today_data(self):
        """
        Получить и проанализировать данные за сегодня
        """
        # Дата с сегодняшнего дня 00:00
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = today.isoformat() + 'Z'
        
        print("=" * 70)
        print(f"АНАЛИТИКА WILDBERRIES ЗА {today.strftime('%d.%m.%Y')}")
        print("=" * 70)
        
        # Получаем все данные
        print("\n🔄 Загрузка данных...")
        orders = self.get_orders(date_from) or []
        all_sales = self.get_sales(date_from) or []
        returns_api = self.get_returns(date_from) or []
        
        # Фильтруем выкупы от возвратов
        real_sales, returns_from_sales = self.filter_real_sales(all_sales)
        
        # Объединяем возвраты из разных источников
        all_returns = returns_from_sales + returns_api
        
        # Находим отказы
        cancellations = self.find_cancellations_from_orders(orders, real_sales)
        
        print("✅ Данные загружены")
        
        # 📦 ВСЕ ЗАКАЗЫ
        print("\n📦 ВСЕ ЗАКАЗЫ СЕГОДНЯ:")
        if orders:
            total_orders = len(orders)
            total_orders_sum = sum(self.get_price_with_discount(order) for order in orders)
            
            print(f"Всего заказов: {total_orders}")
            print(f"Общая сумма заказов: {total_orders_sum:.2f} руб.")
            
            if orders:
                print("\nПоследние 5 заказов:")
                for i, order in enumerate(orders[:5], 1):
                    price = self.get_price_with_discount(order)
                    print(f"  {i}. Заказ: {order.get('odid', 'N/A')}, "
                          f"Артикул: {order.get('nmId', 'N/A')}, "
                          f"Цена: {price:.2f} руб., "
                          f"Дата: {self.format_date(order.get('date', ''))}")
        else:
            print("Нет данных о заказах")
        
        # 💰 РЕАЛЬНЫЕ ВЫКУПЫ (без возвратов)
        print(f"\n💰 РЕАЛЬНЫЕ ВЫКУПЫ СЕГОДНЯ:")
        if real_sales:
            total_sales = len(real_sales)
            total_sales_sum = sum(self.get_price_with_discount(sale) for sale in real_sales)
            
            print(f"Выкупленных позиций: {total_sales}")
            print(f"Общая сумма выкупов: {total_sales_sum:.2f} руб.")
            
            # Детализация выкупов
            print(f"\n📋 ДЕТАЛИЗАЦИЯ ВЫКУПОВ ({total_sales} позиций):")
            for i, sale in enumerate(real_sales, 1):
                price = self.get_price_with_discount(sale)
                print(f"  {i}. Заказ: {sale.get('odid', 'N/A')}, "
                      f"Артикул: {sale.get('nmId', 'N/A')}, "
                      f"Цена: {price:.2f} руб., "
                      f"Дата: {self.format_date(sale.get('date', ''))}")
        else:
            print("Нет данных о выкупах")
        
        # ❌ ОТКАЗЫ (невыкупленные заказы)
        print(f"\n❌ ОТКАЗЫ СЕГОДНЯ:")
        if cancellations:
            total_cancellations = len(cancellations)
            total_cancellations_sum = sum(self.get_price_with_discount(order) for order in cancellations)
            
            print(f"Отказов: {total_cancellations}")
            print(f"Сумма отказов: {total_cancellations_sum:.2f} руб.")
            
            print(f"\n📋 АРТИКУЛЫ ОТКАЗАННЫХ ТОВАРОВ:")
            unique_articles = set()
            for i, cancellation in enumerate(cancellations, 1):
                article = cancellation.get('nmId', 'N/A')
                price = self.get_price_with_discount(cancellation)
                unique_articles.add(article)
                print(f"  {i}. Артикул: {article}, "
                      f"Цена: {price:.2f} руб., "
                      f"Заказ: {cancellation.get('odid', 'N/A')}, "
                      f"Дата: {self.format_date(cancellation.get('date', ''))}")
            
            print(f"\n📊 Уникальных артикулов с отказами: {len(unique_articles)}")
            print("🔍 Список артикулов:", ", ".join(str(art) for art in unique_articles))
            
        else:
            print("Нет данных об отказах")
            print("Проверяем данные...")
            print(f"Всего заказов: {len(orders)}")
            print(f"Всего выкупов: {len(real_sales)}")
            if orders and real_sales:
                order_ids = [str(order.get('odid', '')) for order in orders]
                sale_ids = [str(sale.get('odid', '')) for sale in real_sales]
                print(f"ID заказов: {order_ids[:5]}...")
                print(f"ID выкупов: {sale_ids[:5]}...")
        
        # 🔄 ВОЗВРАТЫ
        print(f"\n🔄 ВОЗВРАТЫ СЕГОДНЯ:")
        if all_returns:
            total_returns = len(all_returns)
            total_returns_sum = abs(sum(self.get_price_with_discount(sale) for sale in all_returns))
            
            print(f"Возвратов позиций: {total_returns}")
            print(f"Общая сумма возвратов: {total_returns_sum:.2f} руб.")
        else:
            print("Нет данных о возвратах")
        
        # 📊 СВОДКА И КОНВЕРСИЯ
        print("\n📊 СВОДКА ЗА СЕГОДНЯ:")
        
        if orders:
            total_orders_count = len(orders)
            total_sales_count = len(real_sales) if real_sales else 0
            total_cancellations_count = len(cancellations)
            total_returns_count = len(all_returns) if all_returns else 0
            
            # Конверсия из заказов в выкупы
            conversion_to_sales = (total_sales_count / total_orders_count * 100) if total_orders_count > 0 else 0
            
            # Процент отказов
            cancellation_rate = (total_cancellations_count / total_orders_count * 100) if total_orders_count > 0 else 0
            
            print(f"📦 Всего заказов: {total_orders_count}")
            print(f"💰 Реальных выкупов: {total_sales_count}")
            print(f"❌ Отказов: {total_cancellations_count}")
            print(f"🔄 Возвратов: {total_returns_count}")
            print(f"📈 Конверсия в выкупы: {conversion_to_sales:.1f}%")
            print(f"📉 Процент отказов: {cancellation_rate:.1f}%")
        
        return {
            'orders': orders,
            'real_sales': real_sales,
            'cancellations': cancellations,
            'returns': all_returns
        }

def load_token_from_env():
    """
    Загружает токен из файла .env из папки на уровень выше
    """
    parent_dir = Path(__file__).parent.parent
    env_file = parent_dir / '.env'
    
    print(f"🔍 Ищем файл .env по пути: {env_file}")
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        if key.strip() == 'Token_wb':
                            token = value.strip()
                            if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
                                token = token[1:-1]
                            print("✅ Токен найден в .env файле")
                            return token
        except Exception as e:
            print(f"❌ Ошибка при чтении .env файла: {e}")
    
    print("❌ Файл .env не найден или токен Token_wb не найден в файле")
    return None

def main():
    """
    Основная функция для запуска парсера
    """
    api_token = load_token_from_env()
    
    if not api_token:
        print("❌ Не удалось загрузить токен!")
        return
    
    parser = WBAnalyticsParser(api_token)
    
    # Получаем данные за сегодня
    data = parser.analyze_today_data()
    
    # Сохраняем сырые данные в файл для проверки
    if data['orders'] or data['real_sales'] or data['returns']:
        with open('wb_data_check.json', 'w', encoding='utf-8') as f:
            data_to_save = {
                'timestamp': datetime.now().isoformat(),
                'orders': data['orders'],
                'real_sales': data['real_sales'],
                'cancellations': data['cancellations'],
                'returns': data['returns']
            }
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Полные данные сохранены в файл: wb_data_check.json")

if __name__ == "__main__":
    main()