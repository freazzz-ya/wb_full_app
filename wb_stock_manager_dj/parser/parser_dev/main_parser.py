import pandas as pd
import datetime
import time
import requests
import logging
import os
import random
import hashlib
from typing import List, Dict, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import numpy as np
from collections import defaultdict

# Конфигурация
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MOSCOW_TZ = datetime.timezone(datetime.timedelta(hours=3))

DATA_DIR = 'data_parser'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CONFIG = {
    'CITIES': ['Москва'],
    'QUERIES_FILE': 'queries.txt',
    'MAX_PAGE': 10,
    'MAX_PAGE_sellers': 3,
    'BRANDS': ['YalowShop'],
    'SUPPLIERS': ['YalowShop'],
    'REQUEST_DELAY': 1,
    'DATA_FILE': os.path.join(DATA_DIR, 'positions_data.csv'),
    'CATEGORY_HISTORY_FILE': os.path.join(DATA_DIR, 'category_history.csv'),
    'AVG_POSITIONS_FILE': os.path.join(DATA_DIR, 'avg_positions_data.csv'),
    'GLOBAL_AVG_FILE': os.path.join(DATA_DIR, 'global_avg_positions.csv')
}

# Свежие User-Agents и прокси подход
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

class WBParser:
    def __init__(self):
        self.session = requests.Session()
        self._update_headers()
        
    def _update_headers(self):
        """Обновление заголовков со случайным User-Agent"""
        user_agent = random.choice(USER_AGENTS)
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.wildberries.ru/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })

    def load_queries(self):
        """Загрузка запросов из файла"""
        if not os.path.exists(CONFIG['QUERIES_FILE']):
            raise FileNotFoundError(f"Файл с запросами '{CONFIG['QUERIES_FILE']}' не найден")
        
        with open(CONFIG['QUERIES_FILE'], 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
        
        if not queries:
            raise ValueError(f"Файл '{CONFIG['QUERIES_FILE']}' не содержит запросов")
        
        return queries

    def parse_products(self, query):
        """Быстрый парсинг через API с обходом блокировок"""
        results = []
        print(f"🔍 Быстрый парсинг: '{query}'")
        
        for page in range(1, CONFIG['MAX_PAGE'] + 1):
            try:
                # Случайная задержка
                time.sleep(CONFIG['REQUEST_DELAY'] + random.uniform(0.1, 0.3))
                
                # Обновляем заголовки для каждого запроса
                self._update_headers()
                
                # Используем разные dest_id для обхода блокировок
                dest_ids = [-1257786, -1029256, -102269, -2162196, -1257786]
                dest_id = random.choice(dest_ids)
                
                # Основные параметры
                params = {
                    'ab_testing': 'false',
                    'appType': 1,
                    'curr': 'rub',
                    'dest': dest_id,
                    'query': query,
                    'resultset': 'catalog',
                    'sort': 'popular',
                    'spp': 30,
                    'uclusters': 1,
                    'page': page,
                    'lang': 'ru',
                    'locale': 'ru',
                    'timestamp': int(time.time() * 1000)
                }
                
                # Пробуем разные эндпоинты
                endpoints = [
                    'https://search.wb.ru/exactmatch/ru/common/v4/search',
                    'https://search.wb.ru/exactmatch/sng/common/v4/search',
                ]
                
                response = None
                for endpoint in endpoints:
                    try:
                        response = self.session.get(
                            endpoint,
                            params=params,
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            # Проверяем что ответ содержит данные
                            data = response.json()
                            if data and 'data' in data and 'products' in data['data']:
                                break
                    except:
                        continue
                
                if not response or response.status_code != 200:
                    print(f"⚠️ Пропускаем страницу {page} для '{query}'")
                    continue
                    
                data = response.json()
                
                # Извлекаем товары
                products = data.get('data', {}).get('products', [])
                
                if not products:
                    break
                    
                # Обрабатываем товары
                page_target_count = 0
                for idx, product in enumerate(products):
                    if self.is_target_product(product):
                        global_idx = (page - 1) * 100 + idx + 1
                        results.append(self.process_product(product, query, page, idx, global_idx))
                        page_target_count += 1
                
                print(f"📄 Страница {page}: {len(products)} товаров, {page_target_count} целевых")
                
                # Если товаров меньше 100, значит это последняя страница
                if len(products) < 100:
                    break
                    
            except Exception as e:
                print(f"❌ Ошибка на странице {page}: {e}")
                continue
        
        print(f"✅ Запрос '{query}': {len(results)} целевых товаров")
        return results

    def is_target_product(self, product):
        """Проверка, является ли товар целевым"""
        if not isinstance(product, dict):
            return False
            
        brand = product.get('brand', '').strip().lower()
        supplier = product.get('supplier', '').strip()
        return brand in [b.lower() for b in CONFIG['BRANDS']] or supplier in CONFIG['SUPPLIERS']

    def process_product(self, product, query, page, idx, global_idx):
        """Обработка данных товара"""
        log_data = product.get('log', {})
        
        return {
            'Название': product.get('name', ''),
            'Позиция': global_idx,
            'Промо позиция': log_data.get('promoPosition'),
            'Орг. позиция': log_data.get('position', idx + 1),
            'Запрос': query,
            'Дата': datetime.datetime.now(MOSCOW_TZ),
            'Промо': 'Да' if log_data.get('promoPosition') is not None else 'Нет',
            'Город': 'Москва',
            'Артикул': product.get('id', ''),
            'Бренд': product.get('brand', ''),
            'Поставщик': product.get('supplier', ''),
            'Категория': product.get('subjectName', product.get('entity', '')),
            'Цена': product.get('salePriceU', '') // 100 if product.get('salePriceU') else ''
        }

class WBAnalytics:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.avg_positions_file = CONFIG['AVG_POSITIONS_FILE']
        self.global_avg_file = CONFIG['GLOBAL_AVG_FILE']
        self.df = self._load_data()
        self.avg_df = self._load_avg_data()
        self.global_avg_df = self._load_global_avg_data()

    def _load_global_avg_data(self) -> pd.DataFrame:
        """Загрузка данных общих средних позиций"""
        try:
            if os.path.exists(self.global_avg_file):
                df = pd.read_csv(self.global_avg_file)
                df['Дата'] = pd.to_datetime(df['Дата'])
                return df
        except Exception as e:
            logger.error(f"Ошибка загрузки общих средних позиций: {e}")
        return pd.DataFrame(columns=['Дата', 'Средняя_позиция'])

    def update_category_history(self, category):
        """Обновление истории средней позиции по категории"""
        try:
            if self.df.empty:
                logger.warning("DataFrame пуст")
                return False
                
            category_df = self.df[self.df['Категория'] == category]
            if category_df.empty:
                logger.warning(f"Категория {category} не найдена")
                return False
                
            current_avg = round(category_df['Позиция'].mean(), 1)
            current_time = datetime.datetime.now(MOSCOW_TZ)
            
            history_file = CONFIG['CATEGORY_HISTORY_FILE']
            
            new_record = {
                'Категория': category,
                'Дата': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Средняя_позиция': current_avg
            }
            
            if os.path.exists(history_file):
                try:
                    existing_data = pd.read_csv(history_file)
                    updated_data = pd.concat([existing_data, pd.DataFrame([new_record])], ignore_index=True)
                    logger.info(f"Добавлена запись к существующим {len(existing_data)}")
                except Exception as e:
                    logger.warning(f"Ошибка чтения файла истории: {e}, создаем новый")
                    updated_data = pd.DataFrame([new_record])
            else:
                updated_data = pd.DataFrame([new_record])
                logger.info("Создан новый файл истории")
            
            updated_data.to_csv(history_file, index=False)
            logger.info(f"Добавлена запись: {category} - {current_avg}. Всего записей: {len(updated_data)}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении истории: {e}", exc_info=True)
            return False

    def update_global_avg_positions(self, new_data: pd.DataFrame):
        """Обновление общих средних позиций"""
        try:
            if new_data.empty:
                return

            global_avg = round(new_data['Позиция'].mean(), 1)
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            new_record = pd.DataFrame({
                'Дата': [current_time],
                'Средняя_позиция': [global_avg]
            })

            if os.path.exists(self.global_avg_file):
                history = pd.read_csv(self.global_avg_file)
                updated = pd.concat([history, new_record])
            else:
                updated = new_record

            updated.to_csv(self.global_avg_file, index=False)
            logger.info(f"Обновлены общие средние позиций. Текущее значение: {global_avg}")

        except Exception as e:
            logger.error(f"Ошибка обновления общих средних позиций: {e}")

    def _load_data(self) -> pd.DataFrame:
        """Загрузка основных данных"""
        try:
            if os.path.exists(self.data_file):
                df = pd.read_csv(self.data_file)
                df['Дата'] = pd.to_datetime(df['Дата'])
                df['Артикул'] = df['Артикул'].astype(str)
                    
                logger.info(f"Данные загружены: {len(df)} записей")
                return df
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(columns=['Артикул', 'Название', 'Категория', 'Позиция', 'Дата', 'Запрос', 'Промо', 'Цена', 'Бренд'])

    def _load_avg_data(self) -> pd.DataFrame:
        """Загрузка данных средних позиций"""
        try:
            if os.path.exists(self.avg_positions_file):
                df = pd.read_csv(self.avg_positions_file)
                df['Дата'] = pd.to_datetime(df['Дата'])
                return df
        except Exception as e:
            logger.error(f"Ошибка загрузки средних позиций: {e}")
        return pd.DataFrame(columns=['Артикул', 'Средняя_позиция', 'Дата'])

    def update_avg_positions(self, new_data: pd.DataFrame):
        """Обновление средних позиций БЕЗ очистки файла"""
        try:
            if new_data.empty:
                return

            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_avg = new_data.groupby('Артикул').agg({
                'Позиция': 'mean'
            }).reset_index()
            new_avg['Средняя_позиция'] = new_avg['Позиция'].round(1)
            new_avg['Дата'] = current_time
            new_avg = new_avg[['Артикул', 'Средняя_позиция', 'Дата']]

            if os.path.exists(self.avg_positions_file):
                existing_data = pd.read_csv(self.avg_positions_file)
            else:
                existing_data = pd.DataFrame(columns=['Артикул', 'Средняя_позиция', 'Дата'])

            updated_data = pd.concat([existing_data, new_avg], ignore_index=True)
            updated_data.to_csv(self.avg_positions_file, index=False)
            logger.info(f"Добавлены новые средние позиции. Всего записей: {len(updated_data)}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления средних позиций: {e}")

    def get_available_articles(self) -> List[str]:
        """Получение списка доступных артикулов"""
        return sorted(self.df['Артикул'].astype(str).unique().tolist()) if not self.df.empty else []

    def get_product_data(self, article: str):
        """Получение данных по товару"""
        try:
            article_str = str(article).strip()
            product_data = self.df[
                (self.df['Артикул'].astype(str) == article_str) | 
                (self.df['Артикул'].astype(int).astype(str) == article_str)
            ]
            
            if product_data.empty:
                return None, None
                
            stats = {
                'name': product_data['Название'].iloc[0],
                'category': product_data['Категория'].iloc[0],
                'first_check': product_data['Дата'].min().strftime('%d.%m.%Y'),
                'last_check': product_data['Дата'].max().strftime('%d.%m.%Y'),
                'queries_count': product_data['Запрос'].nunique(),
                'avg_position': round(product_data['Позиция'].mean(), 1),
                'best_position': product_data['Позиция'].min(),
                'worst_position': product_data['Позиция'].max(),
                'promo_percentage': round((product_data['Промо'] == 'Да').mean() * 100, 1)
            }
            
            return product_data, stats
        except Exception as e:
            logger.error(f"Ошибка получения данных товара: {e}")
            return None, None

    def get_available_categories(self) -> List[str]:
        """Получение списка категорий"""
        try:
            return self.df['Категория'].unique().tolist()
        except Exception as e:
            logger.error(f"Ошибка получения категорий: {e}")
            return []

    def get_available_queries(self) -> List[str]:
        """Получение списка запросов"""
        try:
            return self.df['Запрос'].unique().tolist()
        except Exception as e:
            logger.error(f"Ошибка получения запросов: {e}")
            return []

class WBParserService:
    """Основной сервис для работы с парсером"""
    
    def __init__(self):
        self.parser = WBParser()
        self.previous_data = None
        self.current_data = None
        self.last_check_time = None

    def check_positions(self):
        """Быстрая проверка позиций через API"""
        print("=" * 60)
        print("🚀 БЫСТРЫЙ ПАРСИНГ ЧЕРЕЗ API")
        print("=" * 60)
        
        try:
            # Проверяем файл запросов
            print("📁 Проверяем файл запросов...")
            queries = self.parser.load_queries()
            print(f"✅ Загружено запросов: {len(queries)}")
            
            # Собираем новые данные
            data = []
            
            for i, query in enumerate(queries, 1):
                print(f"\n{'='*40}")
                print(f"📋 ЗАПРОС {i}/{len(queries)}: '{query}'")
                print(f"{'='*40}")
                
                products = self.parser.parse_products(query)
                data.extend(products)
                print(f"📦 Итого: {len(products)} целевых товаров")
                
                # Минимальная задержка между запросами
                if i < len(queries):
                    time.sleep(0.5)
            
            print(f"\n{'='*60}")
            print("📊 СВОДКА")
            print(f"{'='*60}")
            
            if not data:
                print("❌ НЕ УДАЛОСЬ СОБРАТЬ ДАННЫЕ!")
                return False
                
            print(f"✅ УСПЕШНО: {len(data)} целевых товаров")
            
            # Сохраняем новые данные
            self.current_data = pd.DataFrame(data)
            self.current_data.to_csv(CONFIG['DATA_FILE'], index=False)
            print(f"💾 Данные сохранены в: {CONFIG['DATA_FILE']}")
            
            # Обновляем аналитику
            print("📈 Обновляем аналитику...")
            analytics = WBAnalytics(CONFIG['DATA_FILE'])
            analytics.update_avg_positions(self.current_data)
            analytics.update_global_avg_positions(self.current_data)
            print("✅ Аналитика обновлена")
            
            print(f"\n🎉 ПРОВЕРКА ЗАВЕРШЕНА ЗА {len(queries) * CONFIG['MAX_PAGE'] * CONFIG['REQUEST_DELAY']} СЕКУНД!")
            return True
            
        except Exception as e:
            print(f"\n💥 ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_queries(self):
        """Загрузка запросов из файла"""
        return self.parser.load_queries()

    def get_analytics(self):
        """Получить объект аналитики"""
        return WBAnalytics(CONFIG['DATA_FILE'])

def main():
    """Основная функция"""
    service = WBParserService()
    
    try:
        while True:
            print("\n" + "="*50)
            print("🛍️  Wildberries Parser (БЫСТРЫЙ)")
            print("="*50)
            print("1. 🔍 Проверить позиции (Быстро)")
            print("2. 📊 Анализ топ продавцов") 
            print("3. 📈 Получить аналитику")
            print("4. 🚪 Выход")
            print("="*50)
            
            choice = input("Выберите действие (1-4): ").strip()
            
            if choice == "1":
                service.check_positions()
            elif choice == "2":
                print("⚠️ Анализ топ продавцов временно недоступен")
            elif choice == "3":
                analytics = service.get_analytics()
                print(f"📊 Доступно артикулов: {len(analytics.get_available_articles())}")
                print(f"📁 Доступно категорий: {len(analytics.get_available_categories())}")
                print(f"🔍 Доступно запросов: {len(analytics.get_available_queries())}")
            elif choice == "4":
                print("👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор")
            
            input("\nНажмите Enter...")
    except KeyboardInterrupt:
        print("\n👋 Завершение...")

if __name__ == '__main__':
    main()