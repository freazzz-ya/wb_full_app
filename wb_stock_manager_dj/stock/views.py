from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta

from .models import Product, UserProfile, StockMovement, AdvertisingCampaign, CampaignDailyStats
from .forms import CustomUserCreationForm, UserProfileForm, APITokenForm, StockMovementForm, ProductForm, CampaignDailyStatsForm, AdvertisingCampaignForm
from .wb_parser import get_wb_simple_service, clear_wb_cache


def home(request):
    """Главная страница"""
    if request.user.is_authenticated:
        return redirect('stock_dashboard')
    return render(request, 'stock/home.html')

def register(request):
    """Регистрация пользователя"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Создаем профиль пользователя
            UserProfile.objects.create(user=user)
            
            # Автоматически логиним пользователя
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('stock_dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'stock/register.html', {'form': form})

def user_login(request):
    """Авторизация пользователя"""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {username}!')
            return redirect('stock_dashboard')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    
    return render(request, 'stock/login.html')

@login_required
def profile(request):
    """Страница профиля пользователя"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Обновляем статистику
    update_user_statistics(request.user)
    
    if request.method == 'POST':
        if 'profile_info' in request.POST:
            profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
            token_form = APITokenForm()
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль успешно обновлен!')
                return redirect('profile')
        elif 'api_token' in request.POST:
            profile_form = UserProfileForm(instance=user_profile)
            token_form = APITokenForm(request.POST)
            if token_form.is_valid():
                token_form.save(user_profile)
                messages.success(request, 'API токен успешно сохранен!')
                return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=user_profile)
        # Не показываем текущий токен в форме
        token_form = APITokenForm()
    
    # Получаем статистику товаров
    user_products = Product.objects.filter(user=request.user)
    total_products = user_products.count()
    in_stock = len([p for p in user_products if p.current_stock > 0])
    low_stock = len([p for p in user_products if 0 < p.current_stock < 10])
    out_of_stock = len([p for p in user_products if p.current_stock == 0])
    
    context = {
        'profile_form': profile_form,
        'token_form': token_form,
        'user_profile': user_profile,
        'total_products': total_products,
        'in_stock': in_stock,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
    }
    return render(request, 'stock/profile.html', context)

@login_required
def stock_dashboard(request):
    """Страница контроля остатков с фильтрами"""
    products = Product.objects.filter(user=request.user)
    
    # Получаем параметры фильтрации
    sort_by = request.GET.get('sort', '-purchase_date')
    search_query = request.GET.get('search', '')
    stock_filter = request.GET.get('stock', '')
    
    # Поиск по названию и артикулу
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(article__icontains=search_query)
        )
    
    # Преобразуем в список для вычисляемых полей
    products_list = list(products)
    
    # Фильтрация по остаткам
    if stock_filter == 'low':
        products_list = [p for p in products_list if 0 < p.current_stock < 50]
    elif stock_filter == 'out':
        products_list = [p for p in products_list if p.current_stock == 0]
    elif stock_filter == 'normal':
        products_list = [p for p in products_list if p.current_stock >= 50]
    
    # Сортировка
    if sort_by == 'current_stock':
        products_list.sort(key=lambda x: x.current_stock)
    elif sort_by == '-current_stock':
        products_list.sort(key=lambda x: x.current_stock, reverse=True)
    elif sort_by == 'name':
        products_list.sort(key=lambda x: x.name.lower())
    elif sort_by == '-name':
        products_list.sort(key=lambda x: x.name.lower(), reverse=True)
    elif sort_by == 'purchase_date':
        products_list.sort(key=lambda x: x.purchase_date)
    elif sort_by == '-purchase_date':
        products_list.sort(key=lambda x: x.purchase_date, reverse=True)
    elif sort_by == 'days_in_stock':
        products_list.sort(key=lambda x: x.days_in_stock)
    elif sort_by == '-days_in_stock':
        products_list.sort(key=lambda x: x.days_in_stock, reverse=True)
    
    # Добавляем вычисляемые поля для каждого товара
    for product in products_list:
        product.total_in = product.total_incoming
        product.total_out = product.total_outgoing
        product.current = product.current_stock
    
    # Статистика для карточек
    total_products = len(products_list)
    in_stock = len([p for p in products_list if p.current_stock > 0])
    low_stock = len([p for p in products_list if 0 < p.current_stock < 10])
    out_of_stock = len([p for p in products_list if p.current_stock == 0])
    
    # Обновляем статистику пользователя
    update_user_statistics(request.user)
    
    context = {
        'products': products_list,
        'page_title': 'Контроль остатков Wildberries',
        'current_sort': sort_by,
        'search_query': search_query,
        'stock_filter': stock_filter,
        'total_products': total_products,
        'in_stock': in_stock,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
    }
    return render(request, 'stock/stock_dashboard.html', context)

def update_user_statistics(user):
    """Обновление статистики пользователя"""
    user_products = Product.objects.filter(user=user)
    total_products = user_products.count()
    in_stock = len([p for p in user_products if p.current_stock > 0])
    low_stock = len([p for p in user_products if 0 < p.current_stock < 10])
    out_of_stock = len([p for p in user_products if p.current_stock == 0])
    
    user.total_products = total_products
    user.total_in_stock = in_stock
    user.low_stock_count = low_stock
    user.out_of_stock_count = out_of_stock
    user.save()


@login_required
def product_list(request):
    """Список товаров пользователя"""
    products = Product.objects.filter(user=request.user)
    return render(request, 'stock/product_list.html', {
        'products': products,
        'page_title': 'Мои товары'
    })

@login_required
def product_add(request):
    """Добавление нового товара"""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            messages.success(request, f'Товар "{product.name}" успешно добавлен!')
            return redirect('product_list')
    else:
        form = ProductForm()
    
    return render(request, 'stock/product_form.html', {
        'form': form,
        'page_title': 'Добавить товар',
        'submit_text': 'Добавить товар'
    })

@login_required
def product_edit(request, product_id):
    """Редактирование товара"""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Товар "{product.name}" успешно обновлен!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'stock/product_form.html', {
        'form': form,
        'page_title': 'Редактировать товар',
        'submit_text': 'Сохранить изменения',
        'product': product
    })

@login_required
def product_delete(request, product_id):
    """Удаление товара"""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Товар "{product_name}" успешно удален!')
        return redirect('product_list')
    
    return render(request, 'stock/product_confirm_delete.html', {
        'product': product
    })

@login_required
def movement_add(request, product_id):
    """Добавление движения товара"""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.product = product
            movement.save()
            messages.success(request, f'Движение товара "{product.name}" добавлено!')
            return redirect('stock_dashboard')
    else:
        form = StockMovementForm()
    
    return render(request, 'stock/movement_form.html', {
        'form': form,
        'product': product,
        'page_title': f'Добавить движение - {product.name}'
    })

@login_required
def product_detail(request, product_id):
    """Детальная страница товара с историей движений"""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    movements = product.movements.all().order_by('-date', '-created_at')
    
    return render(request, 'stock/product_detail.html', {
        'product': product,
        'movements': movements,
        'page_title': f'Товар - {product.name}'
    })

@login_required
def analytics_dashboard(request):
    """Дашборд аналитики Wildberries за сегодня с кэшированием"""
    # Проверяем, не нужно ли обновить данные
    refresh = request.GET.get('refresh')
    if refresh:
        clear_wb_cache(request.user)
    
    service = get_wb_simple_service(request.user)
    
    analytics_data = None
    error = None
    
    if service:
        try:
            # Получаем данные за сегодня с кэшированием
            analytics_data = service.analyze_today_data(request.user.id)
            if not analytics_data['success']:
                error = analytics_data.get('error', 'Не удалось получить данные аналитики')
        except Exception as e:
            error = f"Ошибка при получении данных: {str(e)}"
            analytics_data = {
                'success': False,
                'date': datetime.now().strftime("%d.%m.%Y"),
                'orders': {'count': 0, 'sum': 0, 'data': []},
                'sales': {'count': 0, 'sum': 0, 'data': []},
                'cancellations': {'count': 0, 'sum': 0, 'data': []},
                'returns': {'count': 0, 'sum': 0, 'data': []},
                'conversion_rate': 0,
                'cancellation_rate': 0
            }
    else:
        error = "API токен не настроен. Добавьте токен в профиле."
        analytics_data = {
            'success': False,
            'date': datetime.now().strftime("%d.%m.%Y"),
            'orders': {'count': 0, 'sum': 0, 'data': []},
            'sales': {'count': 0, 'sum': 0, 'data': []},
            'cancellations': {'count': 0, 'sum': 0, 'data': []},
            'returns': {'count': 0, 'sum': 0, 'data': []},
            'conversion_rate': 0,
            'cancellation_rate': 0
        }
    
    context = {
        'page_title': 'Аналитика за сегодня',
        'analytics_data': analytics_data,
        'error': error
    }
    return render(request, 'stock/analytics_dashboard.html', context)

@login_required
def sales_report(request):
    """Детальный отчет по продажам"""
    parser = get_wb_parser_for_user(request.user)
    
    period = request.GET.get('period', '7')
    try:
        period_days = int(period)
    except:
        period_days = 7
    
    report_data = None
    error = None
    
    if parser:
        try:
            report_data = parser.analyze_period_data(period_days)
        except Exception as e:
            error = f"Ошибка при получении отчета: {str(e)}"
    else:
        error = "API токен не настроен. Добавьте токен в профиле."
    
    context = {
        'page_title': 'Отчет по продажам',
        'report_data': report_data,
        'error': error,
        'period_days': period_days
    }
    return render(request, 'stock/sales_report.html', context)

@login_required
def product_analytics(request):
    """Аналитика по товарам"""
    user_products = Product.objects.filter(user=request.user)
    
    # Статистика по товарам
    total_products = user_products.count()
    products_in_stock = len([p for p in user_products if p.current_stock > 0])
    products_low_stock = len([p for p in user_products if 0 < p.current_stock < 10])
    products_out_of_stock = len([p for p in user_products if p.current_stock == 0])
    
    # Товары с самым долгим сроком на складе
    old_products = sorted(user_products, key=lambda x: x.days_in_stock, reverse=True)[:5]
    
    # Товары с малым остатком
    low_stock_products = [p for p in user_products if 0 < p.current_stock < 5]
    
    context = {
        'page_title': 'Аналитика товаров',
        'total_products': total_products,
        'products_in_stock': products_in_stock,
        'products_low_stock': products_low_stock,
        'products_out_of_stock': products_out_of_stock,
        'old_products': old_products,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'stock/product_analytics.html', context)

def documentation(request):
    """Страница документации"""
    context = {
        'page_title': 'Документация'
    }
    return render(request, 'stock/documentation.html', context)

@login_required
def advertising_dashboard(request):
    """Дашборд рекламных кампаний"""
    campaigns = AdvertisingCampaign.objects.filter(user=request.user)
    
    # Статистика по всем кампаниям
    total_campaigns = campaigns.count()
    active_campaigns = campaigns.filter(status='active').count()
    total_spent = sum(float(campaign.total_spent) for campaign in campaigns)
    total_orders = sum(campaign.total_orders for campaign in campaigns)
    
    # Последние кампании
    recent_campaigns = campaigns.order_by('-created_at')[:5]
    
    # График эффективности кампаний
    campaign_stats = []
    for campaign in campaigns:
        if campaign.total_orders > 0:
            campaign_stats.append({
                'name': campaign.name,
                'spent': float(campaign.total_spent),
                'orders': campaign.total_orders,
                'cpo': float(campaign.cpo)
            })
    
    # Подготовка данных для JSON
    campaign_names_json = [stat['name'] for stat in campaign_stats]
    campaign_spent_json = [stat['spent'] for stat in campaign_stats]
    campaign_orders_json = [stat['orders'] for stat in campaign_stats]
    
    context = {
        'page_title': 'Рекламные кампании',
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'total_spent': total_spent,
        'total_orders': total_orders,
        'recent_campaigns': recent_campaigns,
        'campaign_stats': campaign_stats,
        'campaign_names_json': campaign_names_json,
        'campaign_spent_json': campaign_spent_json,
        'campaign_orders_json': campaign_orders_json,
    }
    return render(request, 'stock/advertising_dashboard.html', context)


@login_required
def campaign_list(request):
    """Список всех рекламных кампаний"""
    campaigns = AdvertisingCampaign.objects.filter(user=request.user)
    
    # Фильтрация
    campaign_type = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    
    # Исправляем фильтрацию по типу
    if campaign_type and campaign_type != 'all':
        campaigns = campaigns.filter(campaign_type=campaign_type)
    
    # Исправляем фильтрацию по статусу  
    if status_filter and status_filter != 'all':
        campaigns = campaigns.filter(status=status_filter)
    
    context = {
        'page_title': 'Мои рекламные кампании',
        'campaigns': campaigns,
        'campaign_type_filter': campaign_type,
        'status_filter': status_filter,
    }
    return render(request, 'stock/campaign_list.html', context)


@login_required
def campaign_create(request):
    """Создание новой рекламной кампании"""
    if request.method == 'POST':
        print("POST данные:", request.POST)
        print("Выбранные товары:", request.POST.getlist('products'))
        
        form = AdvertisingCampaignForm(request.POST, user=request.user)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.save()
            form.save_m2m()  # Сохраняем товары
            messages.success(request, f'Кампания "{campaign.name}" создана!')
            return redirect('campaign_list')
        else:
            print("Ошибки формы:", form.errors)
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = AdvertisingCampaignForm(user=request.user)
    
    context = {
        'page_title': 'Создать рекламную кампанию',
        'form': form,
        'submit_text': 'Создать кампанию'
    }
    return render(request, 'stock/campaign_form.html', context)


@login_required
def campaign_detail(request, campaign_id):
    """Детальная страница кампании со статистикой"""
    campaign = get_object_or_404(AdvertisingCampaign, id=campaign_id, user=request.user)
    daily_stats = campaign.daily_stats.all().order_by('date')  # Изменили на порядок от старых к новым
    
    # Форма для добавления статистики
    if request.method == 'POST':
        stats_form = CampaignDailyStatsForm(request.POST)
        if stats_form.is_valid():
            daily_stat = stats_form.save(commit=False)
            daily_stat.campaign = campaign
            
            # Проверяем, нет ли уже статистики за эту дату
            existing_stat = CampaignDailyStats.objects.filter(
                campaign=campaign, 
                date=daily_stat.date
            ).first()
            
            if existing_stat:
                # Обновляем существующую запись
                existing_stat.views = daily_stat.views
                existing_stat.clicks = daily_stat.clicks
                existing_stat.cart_adds = daily_stat.cart_adds
                existing_stat.orders = daily_stat.orders
                existing_stat.spent = daily_stat.spent
                existing_stat.save()
                messages.success(request, f'Статистика за {daily_stat.date} обновлена!')
            else:
                # Создаем новую запись
                daily_stat.save()
                messages.success(request, f'Статистика за {daily_stat.date} добавлена!')
            
            return redirect('campaign_detail', campaign_id=campaign_id)
    else:
        stats_form = CampaignDailyStatsForm()
    
    # Данные для графиков (берем последние 30 записей)
    recent_stats = daily_stats.order_by('-date')[:30]
    dates = [stat.date.strftime('%d.%m') for stat in recent_stats]
    spends = [float(stat.spent) for stat in recent_stats]
    orders = [stat.orders for stat in recent_stats]
    clicks = [stat.clicks for stat in recent_stats]
    views = [stat.views for stat in recent_stats]
    
    context = {
        'page_title': f'Кампания: {campaign.name}',
        'campaign': campaign,
        'daily_stats': daily_stats.order_by('-date'),  # Для таблицы - новые сверху
        'stats_form': stats_form,
        'chart_data': {
            'dates': dates,
            'spends': spends,
            'orders': orders,
            'clicks': clicks,
            'views': views,
        }
    }
    return render(request, 'stock/campaign_detail.html', context)

@login_required
def campaign_edit(request, campaign_id):
    """Редактирование кампании"""
    campaign = get_object_or_404(AdvertisingCampaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        form = AdvertisingCampaignForm(request.POST, instance=campaign, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Кампания "{campaign.name}" обновлена!')
            return redirect('campaign_list')
    else:
        form = AdvertisingCampaignForm(instance=campaign, user=request.user)
    
    context = {
        'page_title': f'Редактировать: {campaign.name}',
        'form': form,
        'submit_text': 'Сохранить изменения',
        'campaign': campaign
    }
    return render(request, 'stock/campaign_form.html', context)


@login_required
def campaign_delete(request, campaign_id):
    """Удаление кампании"""
    campaign = get_object_or_404(AdvertisingCampaign, id=campaign_id, user=request.user)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Кампания "{campaign_name}" удалена!')
        return redirect('campaign_list')
    
    return render(request, 'stock/campaign_confirm_delete.html', {
        'campaign': campaign
    })


@login_required
def advertising_analytics(request):
    """Аналитика эффективности рекламы"""
    campaigns = AdvertisingCampaign.objects.filter(user=request.user)
    
    # Общая статистика
    total_campaigns = campaigns.count()
    total_spent = sum(campaign.total_spent for campaign in campaigns)
    total_orders = sum(campaign.total_orders for campaign in campaigns)
    total_clicks = sum(campaign.total_clicks for campaign in campaigns)
    
    # Самые эффективные кампании (по CPO)
    effective_campaigns = []
    for campaign in campaigns:
        if campaign.total_orders > 0:
            effective_campaigns.append({
                'campaign': campaign,
                'cpo': campaign.cpo,
                'roi': (campaign.total_orders * 1000 - campaign.total_spent) / campaign.total_spent * 100 if campaign.total_spent > 0 else 0
            })
    
    # Сортируем по CPO (чем меньше, тем лучше)
    effective_campaigns.sort(key=lambda x: x['cpo'])
    
    # Статистика по типам кампаний
    search_campaigns = campaigns.filter(campaign_type='search')
    auction_campaigns = campaigns.filter(campaign_type='auction')
    
    context = {
        'page_title': 'Аналитика рекламы',
        'total_campaigns': total_campaigns,
        'total_spent': total_spent,
        'total_orders': total_orders,
        'total_clicks': total_clicks,
        'effective_campaigns': effective_campaigns[:10],
        'search_campaigns_count': search_campaigns.count(),
        'auction_campaigns_count': auction_campaigns.count(),
        'search_campaigns_orders': sum(c.total_orders for c in search_campaigns),
        'auction_campaigns_orders': sum(c.total_orders for c in auction_campaigns),
    }
    return render(request, 'stock/advertising_analytics.html', context)

