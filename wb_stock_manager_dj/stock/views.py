from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Product, UserProfile, StockMovement
from .forms import CustomUserCreationForm, UserProfileForm, APITokenForm, StockMovementForm, ProductForm


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
            profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)  # Добавляем request.FILES
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
        products_list = [p for p in products_list if 0 < p.current_stock < 10]
    elif stock_filter == 'out':
        products_list = [p for p in products_list if p.current_stock == 0]
    elif stock_filter == 'normal':
        products_list = [p for p in products_list if p.current_stock >= 10]
    
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