import requests
import time
from urllib.parse import quote

def search_wb_positions(queries, seller_name, seller_id=None, max_pages=5):
    """
    Парсер позиций на Wildberries
    :param queries: список поисковых запросов
    :param seller_name: название продавца (строка)
    :param seller_id: ID продавца (необязательно, если есть название)
    :param max_pages: сколько страниц выдачи проверять (обычно 5 = 500 товаров)
    :return: словарь {запрос: [(позиция, название товара, артикул, ссылка)]}
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://www.wildberries.ru',
        'Referer': 'https://www.wildberries.ru/'
    }

    results = {}

    for query in queries:
        print(f"\n🔍 Ищем по запросу: '{query}'")
        found_items = []
        position = 0
        page = 1

        while page <= max_pages:
            url = f"https://search.wb.ru/exactmatch/ru/common/v4/search"
            params = {
                'appType': '1',
                'curr': 'rub',
                'dest': '-1257786',
                'query': query,
                'resultset': 'catalog',
                'sort': 'popular',
                'spp': '24',
                'suppressSpellcheck': 'false',
                'page': str(page)
            }

            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                if response.status_code != 200:
                    print(f"  ❌ Ошибка {response.status_code} на странице {page}")
                    break

                data = response.json()
                products = data.get('data', {}).get('products', [])

                if not products:
                    print(f"  ℹ️  Страница {page} пуста. Останавливаемся.")
                    break

                for product in products:
                    position += 1
                    name = product.get('name', '')
                    nm_id = product.get('id')
                    brand = product.get('brand', '')
                    supplier = product.get('supplier', '')  # Название продавца
                    supplier_id = product.get('supplierId')

                    # Проверяем совпадение по названию или ID
                    seller_match = False
                    if seller_id and str(supplier_id) == str(seller_id):
                        seller_match = True
                    elif seller_name.lower() in supplier.lower():
                        seller_match = True

                    if seller_match:
                        link = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
                        found_items.append({
                            'position': position,
                            'name': name,
                            'nm_id': nm_id,
                            'brand': brand,
                            'seller': supplier,
                            'link': link
                        })
                        print(f"  ✅ Найдено на позиции {position}: {name[:50]}...")

                page += 1
                time	del.sleep(0.5)  # защита от бана

            except Exception as e:
                print(f"  ⚠️ Ошибка при запросе: {e}")
                break

        results[query] = found_items

    return results


# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===
if __name__ == "__main__":
    queries = [
        "Чехлы на аирподс",
        "Чехлы на аирподс 2"
    ]

    # Укажи название продавца (точно как на WB!)
    seller_name = "YalowShop"  # ←←←←← ИЗМЕНИ НА СВОЙ
    # seller_id = "123456"  # если знаешь точный ID — можно указать

    positions = search_wb_positions(queries, seller_name, max_pages=10)

    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ПОЗИЦИЙ")
    print("="*60)

    for query, items in positions.items():
        print(f"\nЗапрос: {query}")
        if items:
            for item in items:
                print(f"  Позиция {item['position']}: {item['name'][:60]}...")
                print(f"  Артикул: {item['nm_id']} | Продавец: {item['seller']}")
                print(f"  Ссылка: {item['link']}\n")
        else:
            print("  Товары этого продавца не найдены в топе.")