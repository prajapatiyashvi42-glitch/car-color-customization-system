import logging
from decimal import Decimal
from io import BytesIO

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.contrib import messages
from django.template.loader import get_template
from xhtml2pdf import pisa

from .models import (
    CarBrand, CarModel, CarColor, Customer, Service, Order,
    Admin, Booking, Payment, Customization, Feedback, CartItem,
    SavedCustomization, RecentlyViewed, UserFeedback,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_logged_in_customer(request):
    """Return Customer if session is valid, else None."""
    cid = request.session.get('customer_id')
    if not cid:
        return None
    return Customer.objects.filter(pk=cid).first()


def login_required_redirect(request):
    """Redirect to login with a 'next' param."""
    return redirect(f"/login/?next={request.path}")


def _track_recently_viewed(customer, car_model):
    """Upsert a RecentlyViewed record for the customer."""
    if customer:
        RecentlyViewed.objects.update_or_create(
            customer=customer, car_model=car_model
        )


# ─────────────────────────────────────────────
# Public pages
# ─────────────────────────────────────────────

def home(request):
    services = Service.objects.all()[:6]
    return render(request, 'home.html', {'services': services})


def brands(request):
    all_brands = (
        CarBrand.objects
        .filter(brand_id__in=CarColor.objects.filter(stock_quantity__gt=0).values("car_model__brand_id"))
        .distinct()
        .order_by("brand_name")
    )
    return render(request, 'brands.html', {'brands': all_brands})


def models(request, brand_id):
    brand = get_object_or_404(CarBrand, brand_id=brand_id)
    car_models = (
        CarModel.objects
        .filter(model_id__in=CarColor.objects.filter(
            stock_quantity__gt=0, car_model__brand_id=brand_id
        ).values("car_model__model_id"))
        .distinct()
        .order_by("model_name")
    )
    return render(request, 'models.html', {'brand': brand, 'models': car_models})


def customize(request, model_id):
    car = get_object_or_404(CarModel, model_id=model_id)
    colors = CarColor.objects.filter(car_model=car, stock_quantity__gt=0)
    selected_color_id = request.GET.get('color_id')
    customer = get_logged_in_customer(request)

    # Track recently viewed
    _track_recently_viewed(customer, car)

    # Check if this config is already saved
    is_saved = False
    if customer and selected_color_id:
        is_saved = SavedCustomization.objects.filter(
            customer=customer, car_model=car, color_id=selected_color_id
        ).exists()

    return render(request, 'customize.html', {
        'car': car,
        'colors': colors,
        'selected_color_id': selected_color_id,
        'is_logged_in': customer is not None,
        'is_saved': is_saved,
    })


def services(request):
    all_services = Service.objects.all()
    return render(request, 'services.html', {'services': all_services})


def feedback(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        message = request.POST.get('message', '').strip()
        if name and message:
            UserFeedback.objects.create(name=name, message=message)
            messages.success(request, 'Thank you for your feedback!')
            return redirect('feedback')
        else:
            messages.error(request, 'Please fill in both fields.')

    feedbacks = UserFeedback.objects.all()
    return render(request, 'feedback.html', {'feedbacks': feedbacks})


def car_colors(request):
    # Deduplicate by color_code — keep only the first occurrence of each unique color
    seen_codes = set()
    unique_colors = []
    qs = (
        CarColor.objects
        .filter(stock_quantity__gt=0)
        .select_related('car_model', 'car_model__brand')
    )
    for color in qs:
        if color.color_code not in seen_codes:
            seen_codes.add(color.color_code)
            unique_colors.append(color)
        if len(unique_colors) >= 12:
            break
    return render(request, 'car_colors.html', {'colors': unique_colors})


def brand_model_selector(request):
    brands_qs = (
        CarBrand.objects
        .filter(brand_id__in=CarColor.objects.filter(stock_quantity__gt=0).values("car_model__brand_id"))
        .distinct()
        .order_by("brand_name")
    )
    return render(request, 'brand_model_selector.html', {'brands': brands_qs})


def models_by_brand(request, brand_id):
    car_models = (
        CarColor.objects
        .filter(stock_quantity__gt=0, car_model__brand_id=brand_id)
        .values("car_model__model_id", "car_model__model_name")
        .distinct()
        .order_by("car_model__model_name")
    )
    payload = [
        {"model_id": m["car_model__model_id"], "model_name": m["car_model__model_name"]}
        for m in car_models
    ]
    return JsonResponse(payload, safe=False)


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

def register_page(request):
    if get_logged_in_customer(request):
        return redirect('home')

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        password = request.POST.get('password', '')

        # Server-side validation
        errors = {}
        if len(name) < 3:
            errors['name'] = 'Name must be at least 3 characters.'
        if not email or '@' not in email:
            errors['email'] = 'Enter a valid email address.'
        if Customer.objects.filter(email=email).exists():
            errors['email'] = 'This email is already registered.'
        if not phone.isdigit() or len(phone) != 10:
            errors['phone'] = 'Enter a valid 10-digit phone number.'
        if Customer.objects.filter(phone=phone).exists():
            errors['phone'] = 'This phone number is already registered.'
        if len(address) < 10:
            errors['address'] = 'Address must be at least 10 characters.'
        if len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'

        if errors:
            return render(request, 'register.html', {
                'errors': errors,
                'form_data': {'name': name, 'email': email, 'phone': phone, 'address': address},
            })

        customer = Customer(name=name, email=email, phone=phone, address=address)
        customer.set_password(password)
        customer.save()
        messages.success(request, 'Account created! Please log in.')
        return redirect('login')

    return render(request, 'register.html')


def login_page(request):
    if get_logged_in_customer(request):
        return redirect('home')

    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '').strip() or request.GET.get('next', '').strip()

        user = Customer.objects.filter(email=email).first()

        if user and user.check_password(password):
            # Cycle the session key to prevent session fixation
            request.session.cycle_key()
            request.session['customer_id'] = user.customer_id
            request.session['customer_name'] = user.name
            # Only redirect to safe relative URLs
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('home')

        return render(request, 'login.html', {
            'error': 'Invalid email or password. Please try again.',
            'next': next_url,
            'email': email,  # repopulate field
        })

    return render(request, 'login.html', {'next': request.GET.get('next', '').strip()})


def logout_view(request):
    request.session.flush()  # destroys session data + cookie
    return redirect('login')


def profile(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/profile/')

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        gender = request.POST.get('gender', '')

        errors = {}
        if len(name) < 3:
            errors['name'] = 'Name must be at least 3 characters.'
        # Check email uniqueness (excluding self)
        if Customer.objects.filter(email=email).exclude(pk=customer.pk).exists():
            errors['email'] = 'This email is already in use.'
        if Customer.objects.filter(phone=phone).exclude(pk=customer.pk).exists():
            errors['phone'] = 'This phone number is already in use.'

        if not errors:
            customer.name = name
            customer.email = email
            customer.phone = phone
            customer.address = address
            customer.gender = gender
            if request.FILES.get('profile_image'):
                customer.profile_image = request.FILES['profile_image']
            customer.save()
            request.session['customer_name'] = customer.name
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')

        return render(request, 'profile.html', {'customer': customer, 'errors': errors})

    orders = Order.objects.filter(customer=customer).select_related(
        'brand', 'model', 'color'
    ).order_by('-order_date')

    bookings = Booking.objects.filter(customer=customer).select_related(
        'service'
    ).order_by('-booking_date')

    saved = SavedCustomization.objects.filter(customer=customer).select_related(
        'car_model', 'car_model__brand', 'color'
    )

    recently_viewed = RecentlyViewed.objects.filter(customer=customer).select_related(
        'car_model', 'car_model__brand'
    )[:8]

    return render(request, 'profile.html', {
        'customer': customer,
        'orders': orders,
        'bookings': bookings,
        'saved_customizations': saved,
        'recently_viewed': recently_viewed,
    })


# ─────────────────────────────────────────────
# Save / unsave customization (AJAX-friendly)
# ─────────────────────────────────────────────

def save_customization(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    customer = get_logged_in_customer(request)
    if not customer:
        return JsonResponse({'error': 'login_required'}, status=401)

    model_id = request.POST.get('model_id')
    color_id = request.POST.get('color_id')

    car_model = get_object_or_404(CarModel, pk=model_id)
    color = get_object_or_404(CarColor, pk=color_id)

    obj, created = SavedCustomization.objects.get_or_create(
        customer=customer, car_model=car_model, color=color
    )
    if not created:
        obj.delete()
        return JsonResponse({'saved': False})
    return JsonResponse({'saved': True})


# ─────────────────────────────────────────────
# Service booking
# ─────────────────────────────────────────────

def book_service(request, service_id):
    service = get_object_or_404(Service, pk=service_id)
    customer = get_logged_in_customer(request)

    if request.method == "POST":
        schedule_date = request.POST.get("schedule_date")
        if not schedule_date:
            return render(request, "service_booking.html", {
                "service": service,
                "error": "Please select a schedule date.",
                "customer": customer,
            })

        # Guest users must provide contact info
        if not customer:
            name = request.POST.get("name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()
            address = request.POST.get("address", "").strip()

            customer = Customer.objects.filter(email=email).first()
            if not customer:
                customer = Customer.objects.filter(phone=phone).first()
            if not customer:
                customer = Customer.objects.create(
                    name=name, email=email, phone=phone, address=address, password=""
                )
            request.session["customer_id"] = customer.customer_id
            request.session["customer_name"] = customer.name

        booking = Booking.objects.create(
            customer=customer,
            service=service,
            schedule_date=schedule_date,
            status="Pending Payment",
        )
        return render(request, "payment.html", {"booking": booking, "is_service": True})

    return render(request, "service_booking.html", {"service": service, "customer": customer})


# ─────────────────────────────────────────────
# Cart
# ─────────────────────────────────────────────

def add_to_cart(request):
    if request.method != "POST":
        return redirect('car_colors')

    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/cart/')

    item_type = request.POST.get('item_type', 'color')

    if item_type == 'color':
        color = get_object_or_404(CarColor, pk=request.POST.get('item_id'))
        if not CartItem.objects.filter(customer=customer, item_type='color', color=color).exists():
            CartItem.objects.create(customer=customer, item_type='color', color=color)

    elif item_type == 'service':
        service = get_object_or_404(Service, pk=request.POST.get('item_id'))
        if not CartItem.objects.filter(customer=customer, item_type='service', service=service).exists():
            CartItem.objects.create(customer=customer, item_type='service', service=service)

    elif item_type == 'custom':
        model_id = request.POST.get('model_id')
        color_id = request.POST.get('color_id')
        if not color_id:
            return redirect('brand_model_selector')
        car_model = get_object_or_404(CarModel, pk=model_id)
        color = get_object_or_404(CarColor, pk=color_id)
        config = {
            'model_id': car_model.model_id,
            'color_id': color.id,
            'brand': car_model.brand.brand_name,
            'model': car_model.model_name,
            'color': color.color_name,
            'color_code': color.color_code,
            'price': float(car_model.price),
        }
        CartItem.objects.create(customer=customer, item_type='custom', custom_config=config)

    return redirect('cart')


def cart(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/cart/')

    cart_items = CartItem.objects.filter(customer=customer).select_related(
        'color', 'color__car_model', 'color__car_model__brand', 'service'
    )
    total = sum(Decimal(item.get_price()) for item in cart_items)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total})


def remove_from_cart(request, item_id):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    item = get_object_or_404(CartItem, pk=item_id, customer__customer_id=customer.customer_id)
    item.delete()
    return redirect('cart')


def cart_checkout(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/cart/checkout/')

    cart_items = CartItem.objects.filter(customer=customer).select_related(
        'color', 'color__car_model', 'color__car_model__brand', 'service'
    )
    if not cart_items.exists():
        return redirect('cart')

    total = sum(item.get_price() for item in cart_items)
    return render(request, 'cart_checkout.html', {'cart_items': cart_items, 'total': total})


def cart_payment_confirm(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    if request.method != "POST":
        return redirect('cart')

    payment_method = request.POST.get('payment_method', 'card')
    cart_items = list(CartItem.objects.filter(customer=customer).select_related(
        'color', 'color__car_model', 'color__car_model__brand', 'service'
    ))

    orders = []
    bookings = []

    with transaction.atomic():
        for item in cart_items:
            if item.item_type == 'color' and item.color:
                o = Order.objects.create(
                    customer=customer,
                    brand=item.color.car_model.brand,
                    model=item.color.car_model,
                    color=item.color,
                    status="Success" if payment_method != "cod" else "Pending (COD)",
                )
                if item.color.stock_quantity > 0:
                    item.color.stock_quantity -= 1
                    item.color.save()
                orders.append(o)

            elif item.item_type == 'service' and item.service:
                b = Booking.objects.create(
                    customer=customer,
                    service=item.service,
                    schedule_date=timezone.now().date(),
                    status="Success" if payment_method != "cod" else "Pending (COD)",
                )
                Payment.objects.create(
                    booking=b,
                    amount=item.service.price,
                    payment_method=payment_method,
                    status="Success" if payment_method != "cod" else "Pending",
                )
                bookings.append(b)

            elif item.item_type == 'custom' and item.custom_config:
                cfg = item.custom_config
                try:
                    car_model = CarModel.objects.get(pk=cfg['model_id'])
                    color = CarColor.objects.get(pk=cfg['color_id'])
                    o = Order.objects.create(
                        customer=customer,
                        brand=car_model.brand,
                        model=car_model,
                        color=color,
                        status="Success" if payment_method != "cod" else "Pending (COD)",
                    )
                    if color.stock_quantity > 0:
                        color.stock_quantity -= 1
                        color.save()
                    orders.append(o)
                except (CarModel.DoesNotExist, CarColor.DoesNotExist):
                    pass

        CartItem.objects.filter(customer=customer).delete()

    return render(request, 'cart_order_success.html', {
        'orders': orders,
        'bookings': bookings,
        'customer': customer,
    })


# ─────────────────────────────────────────────
# Direct order (from customize page)
# ─────────────────────────────────────────────

def order(request):
    if request.method != "POST":
        return redirect("home")

    customer = get_logged_in_customer(request)
    model_id = request.POST.get("model_id")
    color_id = request.POST.get("color_id")

    if not color_id:
        car = get_object_or_404(CarModel, pk=model_id)
        colors = CarColor.objects.filter(car_model=car, stock_quantity__gt=0)
        return render(request, "customize.html", {
            "car": car, "colors": colors, "error": "Please select a color."
        })

    car_model = get_object_or_404(CarModel, pk=model_id)
    color = get_object_or_404(CarColor, pk=color_id)

    # Guest checkout — create a lightweight customer record
    if not customer:
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        customer = Customer.objects.filter(email=email).first()
        if not customer:
            customer = Customer.objects.filter(phone=phone).first()
        if not customer:
            customer = Customer.objects.create(
                name=request.POST.get("name", ""),
                email=email,
                phone=phone,
                address=request.POST.get("address", ""),
                password="",
            )
        request.session["customer_id"] = customer.customer_id
        request.session["customer_name"] = customer.name

    order_obj = Order.objects.create(
        customer=customer,
        brand=car_model.brand,
        model=car_model,
        color=color,
        status="Pending Payment",
    )
    return render(request, "payment.html", {"order": order_obj})


def payment_confirm(request):
    if request.method != "POST":
        return redirect("home")

    order_id = request.POST.get("order_id")
    booking_id = request.POST.get("booking_id")
    payment_method = request.POST.get("payment_method", "card")

    if order_id:
        order_obj = get_object_or_404(Order, pk=order_id)
        order_obj.status = "Success" if payment_method != "cod" else "Pending (COD)"
        order_obj.save()

        Payment.objects.create(
            booking=None,
            amount=order_obj.model.price,
            payment_method=payment_method,
            status="Success" if payment_method != "cod" else "Pending",
        )

        with transaction.atomic():
            color = order_obj.color
            if color.stock_quantity > 0:
                color.stock_quantity -= 1
                color.save()

        return render(request, "order_success.html", {"order": order_obj})

    elif booking_id:
        booking = get_object_or_404(Booking, pk=booking_id)
        booking.status = "Success" if payment_method != "cod" else "Pending (COD)"
        booking.save()

        Payment.objects.create(
            booking=booking,
            amount=booking.service.price,
            payment_method=payment_method,
            status="Success" if payment_method != "cod" else "Pending",
        )
        return render(request, "booking_success.html", {"booking": booking})

    return redirect("home")


# ─────────────────────────────────────────────
# Custom Admin Panel
# ─────────────────────────────────────────────

def admin_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        admin = Admin.objects.filter(username=username, password=password).first()
        if admin:
            request.session['admin_id'] = admin.admin_id
            request.session['admin_username'] = admin.username
            return redirect('admin_dashboard')
        return render(request, 'admin/login.html', {'error': 'Invalid credentials'})
    return render(request, 'admin/login.html')


def admin_dashboard(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    total_colors = CarColor.objects.count()
    total_orders = Order.objects.count()
    total_customers = Customer.objects.count()
    total_bookings = Booking.objects.count()
    recent_orders = Order.objects.select_related('customer', 'brand', 'model', 'color').order_by('-order_date')[:5]
    low_stock = CarColor.objects.filter(stock_quantity__lte=2).select_related('car_model', 'car_model__brand')

    return render(request, "admin/dashboard.html", {
        "total_colors": total_colors,
        "total_orders": total_orders,
        "total_customers": total_customers,
        "total_bookings": total_bookings,
        "recent_orders": recent_orders,
        "low_stock": low_stock,
    })


def admin_analytics(request):
    """Analytics dashboard — all chart data serialised to JSON for Chart.js."""
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    import json
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth

    # ── 1. Bar chart: orders per brand ──────────────────────────────
    brand_qs = (
        Order.objects
        .values('brand__brand_name')
        .annotate(total=Count('order_id'))
        .order_by('-total')
    )
    brand_labels = [r['brand__brand_name'] for r in brand_qs]
    brand_data   = [r['total'] for r in brand_qs]

    # ── 2. Pie chart: color popularity ──────────────────────────────
    color_qs = (
        Order.objects
        .values('color__color_name', 'color__color_code')
        .annotate(total=Count('order_id'))
        .order_by('-total')[:8]
    )
    color_labels = [r['color__color_name'] for r in color_qs]
    color_data   = [r['total'] for r in color_qs]
    color_codes  = [r['color__color_code'] or '#cccccc' for r in color_qs]

    # ── 3. Line chart: bookings per month ───────────────────────────
    booking_qs = (
        Booking.objects
        .annotate(month=TruncMonth('booking_date'))
        .values('month')
        .annotate(total=Count('booking_id'))
        .order_by('month')
    )
    booking_labels = [r['month'].strftime('%b %Y') for r in booking_qs]
    booking_data   = [r['total'] for r in booking_qs]

    # ── 4. Doughnut chart: order status breakdown ───────────────────
    status_qs = (
        Order.objects
        .values('status')
        .annotate(total=Count('order_id'))
        .order_by('-total')
    )
    status_labels = [r['status'] for r in status_qs]
    status_data   = [r['total'] for r in status_qs]

    # ── 5. Bar chart: revenue per brand (model price × orders) ──────
    revenue_qs = (
        Order.objects
        .values('brand__brand_name')
        .annotate(revenue=Sum('model__price'))
        .order_by('-revenue')
    )
    revenue_labels = [r['brand__brand_name'] for r in revenue_qs]
    revenue_data   = [float(r['revenue'] or 0) for r in revenue_qs]

    # ── 6. Line chart: customer registrations per month ─────────────
    reg_qs = (
        Customer.objects
        .annotate(month=TruncMonth('reg_date'))
        .values('month')
        .annotate(total=Count('customer_id'))
        .order_by('month')
    )
    reg_labels = [r['month'].strftime('%b %Y') for r in reg_qs]
    reg_data   = [r['total'] for r in reg_qs]

    context = {
        # Bar — orders per brand
        'brand_labels': json.dumps(brand_labels),
        'brand_data':   json.dumps(brand_data),
        # Pie — color popularity
        'color_labels': json.dumps(color_labels),
        'color_data':   json.dumps(color_data),
        'color_codes':  json.dumps(color_codes),
        # Line — bookings per month
        'booking_labels': json.dumps(booking_labels),
        'booking_data':   json.dumps(booking_data),
        # Doughnut — order status
        'status_labels': json.dumps(status_labels),
        'status_data':   json.dumps(status_data),
        # Bar — revenue per brand
        'revenue_labels': json.dumps(revenue_labels),
        'revenue_data':   json.dumps(revenue_data),
        # Line — customer registrations
        'reg_labels': json.dumps(reg_labels),
        'reg_data':   json.dumps(reg_data),
        # Summary cards
        'total_orders':    Order.objects.count(),
        'total_bookings':  Booking.objects.count(),
        'total_customers': Customer.objects.count(),
        'total_revenue':   Order.objects.aggregate(t=Sum('model__price'))['t'] or 0,
    }
    return render(request, 'admin/analytics.html', context)


def admin_colors(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    colors = CarColor.objects.select_related("car_model", "car_model__brand").all()
    return render(request, "admin/colors_list.html", {"colors": colors})


def admin_color_create(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    brands = CarBrand.objects.all()
    car_models = CarModel.objects.all()
    if request.method == "POST":
        model = get_object_or_404(CarModel, pk=request.POST.get("model_id"))
        CarColor.objects.create(
            car_model=model,
            color_name=request.POST.get("color_name"),
            color_code=request.POST.get("color_code"),
            price=request.POST.get("price") or 0,
            stock_quantity=request.POST.get("stock_quantity") or 0,
        )
        return redirect("admin_colors")
    return render(request, "admin/color_form.html", {"brands": brands, "models": car_models})


def admin_color_edit(request, color_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    color = get_object_or_404(CarColor, pk=color_id)
    brands = CarBrand.objects.all()
    car_models = CarModel.objects.all()
    if request.method == "POST":
        model = get_object_or_404(CarModel, pk=request.POST.get("model_id"))
        color.car_model = model
        color.color_name = request.POST.get("color_name")
        color.color_code = request.POST.get("color_code")
        color.price = request.POST.get("price") or 0
        color.stock_quantity = request.POST.get("stock_quantity") or 0
        color.save()
        return redirect("admin_colors")
    return render(request, "admin/color_form.html", {"color": color, "brands": brands, "models": car_models})


def admin_color_delete(request, color_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    color = get_object_or_404(CarColor, pk=color_id)
    if request.method == "POST":
        color.delete()
        return redirect("admin_colors")
    return render(request, "admin/color_confirm_delete.html", {"color": color})


def admin_orders(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    orders = Order.objects.select_related("customer", "brand", "model", "color").order_by("-order_date")
    return render(request, "admin/orders_list.html", {"orders": orders})


# ─────────────────────────────────────────────
# Forgot / Reset Password (custom, no email needed)
# ─────────────────────────────────────────────

def forgot_password(request):
    """Step 1 — user enters email, we verify it exists."""
    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        customer = Customer.objects.filter(email=email).first()
        if customer:
            # Store in session so reset page can use it (dev-only flow)
            request.session['reset_email'] = email
            return redirect('reset_password')
        return render(request, 'forgot_password.html', {
            'error': 'No account found with that email address.'
        })
    return render(request, 'forgot_password.html')


def reset_password(request):
    """Step 2 — user sets a new password."""
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == "POST":
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')

        if len(password) < 6:
            return render(request, 'reset_password.html', {
                'error': 'Password must be at least 6 characters.'
            })
        if password != confirm:
            return render(request, 'reset_password.html', {
                'error': 'Passwords do not match.'
            })

        customer = Customer.objects.filter(email=email).first()
        if customer:
            customer.set_password(password)
            customer.save()
            del request.session['reset_email']
            messages.success(request, 'Password reset successful! Please log in.')
            return redirect('login')

    return render(request, 'reset_password.html')


# ─────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────

def generate_report(request):
    """Generate and return a PDF report of users and car customizations."""
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    total_users = Customer.objects.count()
    total_customizations = Order.objects.count()
    customizations = Order.objects.select_related(
        'customer', 'model', 'color'
    ).order_by('-order_date')

    context = {
        'total_users': total_users,
        'total_customizations': total_customizations,
        'customizations': customizations,
        'generated_at': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
    }

    template = get_template('admin/report.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="car_customization_report.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF report.', status=500)

    return response


# ─────────────────────────────────────────────
# Admin — Brand Management
# ─────────────────────────────────────────────

def admin_brands(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    brands = CarBrand.objects.all().order_by('brand_name')
    return render(request, 'admin/brands_list.html', {'brands': brands})


def admin_brand_create(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    if request.method == 'POST':
        name = request.POST.get('brand_name', '').strip()
        if name:
            CarBrand.objects.get_or_create(brand_name=name)
        return redirect('admin_brands')
    return render(request, 'admin/brand_form.html')


def admin_brand_edit(request, brand_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    brand = get_object_or_404(CarBrand, pk=brand_id)
    if request.method == 'POST':
        brand.brand_name = request.POST.get('brand_name', '').strip()
        brand.save()
        return redirect('admin_brands')
    return render(request, 'admin/brand_form.html', {'brand': brand})


def admin_brand_delete(request, brand_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    brand = get_object_or_404(CarBrand, pk=brand_id)
    if request.method == 'POST':
        brand.delete()
        return redirect('admin_brands')
    return render(request, 'admin/brand_confirm_delete.html', {'brand': brand})


# ─────────────────────────────────────────────
# Admin — Car Model Management
# ─────────────────────────────────────────────

def admin_car_models(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    car_models = CarModel.objects.select_related('brand').order_by('brand__brand_name', 'model_name')
    return render(request, 'admin/car_models_list.html', {'car_models': car_models})


def admin_car_model_create(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    brands = CarBrand.objects.all().order_by('brand_name')
    if request.method == 'POST':
        brand = get_object_or_404(CarBrand, pk=request.POST.get('brand_id'))
        CarModel.objects.create(
            brand=brand,
            model_name=request.POST.get('model_name', '').strip(),
            base_color=request.POST.get('base_color', '').strip(),
            price=request.POST.get('price') or 0,
            preview_image=request.FILES.get('preview_image'),
        )
        return redirect('admin_car_models')
    return render(request, 'admin/car_model_form.html', {'brands': brands})


def admin_car_model_edit(request, model_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    car_model = get_object_or_404(CarModel, pk=model_id)
    brands = CarBrand.objects.all().order_by('brand_name')
    if request.method == 'POST':
        car_model.brand = get_object_or_404(CarBrand, pk=request.POST.get('brand_id'))
        car_model.model_name = request.POST.get('model_name', '').strip()
        car_model.base_color = request.POST.get('base_color', '').strip()
        car_model.price = request.POST.get('price') or 0
        if request.FILES.get('preview_image'):
            car_model.preview_image = request.FILES['preview_image']
        car_model.save()
        return redirect('admin_car_models')
    return render(request, 'admin/car_model_form.html', {'car_model': car_model, 'brands': brands})


def admin_car_model_delete(request, model_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    car_model = get_object_or_404(CarModel, pk=model_id)
    if request.method == 'POST':
        car_model.delete()
        return redirect('admin_car_models')
    return render(request, 'admin/car_model_confirm_delete.html', {'car_model': car_model})


# ─────────────────────────────────────────────
# Admin — Service Management
# ─────────────────────────────────────────────

def admin_services(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    all_services = Service.objects.all().order_by('service_name')
    return render(request, 'admin/services_list.html', {'services': all_services})


def admin_service_create(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    if request.method == 'POST':
        Service.objects.create(
            service_name=request.POST.get('service_name', '').strip(),
            description=request.POST.get('description', '').strip(),
            price=request.POST.get('price') or 0,
            is_active='is_active' in request.POST,
        )
        return redirect('admin_services')
    return render(request, 'admin/service_form.html')


def admin_service_edit(request, service_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    svc = get_object_or_404(Service, pk=service_id)
    if request.method == 'POST':
        svc.service_name = request.POST.get('service_name', '').strip()
        svc.description = request.POST.get('description', '').strip()
        svc.price = request.POST.get('price') or 0
        svc.is_active = 'is_active' in request.POST
        svc.save()
        return redirect('admin_services')
    return render(request, 'admin/service_form.html', {'service': svc})


def admin_service_delete(request, service_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    svc = get_object_or_404(Service, pk=service_id)
    if request.method == 'POST':
        svc.delete()
        return redirect('admin_services')
    return render(request, 'admin/service_confirm_delete.html', {'service': svc})


# ─────────────────────────────────────────────
# Admin — Customizations View
# ─────────────────────────────────────────────

def admin_customizations(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    qs = Customization.objects.select_related('customer', 'model', 'model__brand').order_by('-date')

    # Filters
    user_q = request.GET.get('user', '').strip()
    car_q = request.GET.get('car', '').strip()
    color_q = request.GET.get('color', '').strip()

    if user_q:
        qs = qs.filter(customer__name__icontains=user_q)
    if car_q:
        qs = qs.filter(model__model_name__icontains=car_q)
    if color_q:
        qs = qs.filter(color_option__icontains=color_q)

    return render(request, 'admin/customizations_list.html', {
        'customizations': qs,
        'user_q': user_q, 'car_q': car_q, 'color_q': color_q,
    })


def admin_customization_delete(request, cust_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    c = get_object_or_404(Customization, pk=cust_id)
    if request.method == 'POST':
        c.delete()
    return redirect('admin_customizations')


# ─────────────────────────────────────────────
# Admin — Order Management (status change + filter)
# ─────────────────────────────────────────────

def admin_orders(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    qs = Order.objects.select_related('customer', 'brand', 'model', 'color').order_by('-order_date')

    status_filter = request.GET.get('status', '').strip()
    user_filter = request.GET.get('user', '').strip()
    date_filter = request.GET.get('date', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if user_filter:
        qs = qs.filter(customer__name__icontains=user_filter)
    if date_filter:
        qs = qs.filter(order_date__date=date_filter)

    return render(request, 'admin/orders_list.html', {
        'orders': qs,
        'status_choices': Order.STATUS_CHOICES,
        'status_filter': status_filter,
        'user_filter': user_filter,
        'date_filter': date_filter,
    })


def admin_order_status_update(request, order_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
    if request.method == 'POST':
        o = get_object_or_404(Order, pk=order_id)
        new_status = request.POST.get('status')
        valid = [s[0] for s in Order.STATUS_CHOICES]
        if new_status in valid:
            o.status = new_status
            o.save()
    return redirect('admin_orders')


# ─────────────────────────────────────────────
# User — My Orders + Cancel
# ─────────────────────────────────────────────

def my_orders(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/my-orders/')

    orders = (
        Order.objects
        .filter(customer=customer)
        .prefetch_related('services')
        .select_related('brand', 'model', 'color')
        .order_by('-order_date')
    )
    return render(request, 'my_orders.html', {
        'orders': orders,
        'status_steps': ['Pending', 'Confirmed', 'In Progress', 'Completed'],
    })


def cancel_order(request, order_id):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')

    if request.method == 'POST':
        o = get_object_or_404(Order, pk=order_id, customer=customer)
        if o.status in ('Pending', 'Confirmed', 'Pending Payment', 'Pending (COD)'):
            o.status = 'Cancelled'
            o.save()
            messages.success(request, f'Order #{o.order_id} has been cancelled.')
        else:
            messages.error(request, 'This order cannot be cancelled.')
    return redirect('my_orders')


# ─────────────────────────────────────────────
# Customer — Change Password
# ─────────────────────────────────────────────

def customer_change_password(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect(f'/login/?next=/change-password/')

    if request.method == 'POST':
        old_pw = request.POST.get('old_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm_pw = request.POST.get('confirm_password', '')

        if not customer.check_password(old_pw):
            return render(request, 'change_password.html', {'error': 'Current password is incorrect.'})
        if len(new_pw) < 6:
            return render(request, 'change_password.html', {'error': 'New password must be at least 6 characters.'})
        if new_pw != confirm_pw:
            return render(request, 'change_password.html', {'error': 'New passwords do not match.'})

        customer.set_password(new_pw)
        customer.save(update_fields=['password'])
        messages.success(request, 'Password changed successfully.')
        return redirect('profile')

    return render(request, 'change_password.html')


# ─────────────────────────────────────────────
# Admin — Change Password
# ─────────────────────────────────────────────

def admin_change_password(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    admin = Admin.objects.filter(pk=request.session['admin_id']).first()
    if not admin:
        return redirect('admin_login')

    if request.method == 'POST':
        old_pw = request.POST.get('old_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm_pw = request.POST.get('confirm_password', '')

        from django.contrib.auth.hashers import check_password as django_check, make_password as django_make

        # Support both plain-text legacy passwords and hashed ones
        old_matches = (
            django_check(old_pw, admin.password)
            if admin.password.startswith(('pbkdf2_', 'bcrypt', 'argon2', '!'))
            else admin.password == old_pw
        )

        if not old_matches:
            return render(request, 'admin/change_password.html', {'error': 'Current password is incorrect.'})
        if len(new_pw) < 6:
            return render(request, 'admin/change_password.html', {'error': 'New password must be at least 6 characters.'})
        if new_pw != confirm_pw:
            return render(request, 'admin/change_password.html', {'error': 'New passwords do not match.'})

        admin.password = django_make(new_pw)
        admin.save(update_fields=['password'])
        messages.success(request, 'Admin password changed successfully.')
        return redirect('admin_dashboard')

    return render(request, 'admin/change_password.html')


# ─────────────────────────────────────────────
# Admin — Forgot / Reset Password (token-based, no Django User)
# ─────────────────────────────────────────────

import secrets
from django.core.mail import send_mail

# In-memory token store: {token: admin_id}
# For production, use a DB model or cache instead.
_admin_reset_tokens = {}


def admin_forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        admin = Admin.objects.filter(email=email).first()
        # Always show the same message to prevent email enumeration
        if admin:
            token = secrets.token_urlsafe(32)
            _admin_reset_tokens[token] = admin.admin_id
            reset_url = request.build_absolute_uri(f'/admin-panel/reset-password/{token}/')
            send_mail(
                subject='Admin Password Reset — Car Customizer',
                message=f'Click the link below to reset your admin password:\n\n{reset_url}\n\nThis link is single-use.',
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[admin.email],
                fail_silently=True,
            )
        return render(request, 'admin/forgot_password.html', {
            'sent': True,
            'email': email,
        })
    return render(request, 'admin/forgot_password.html')


def admin_reset_password(request, token):
    admin_id = _admin_reset_tokens.get(token)
    if not admin_id:
        return render(request, 'admin/reset_password.html', {'invalid': True})

    admin = Admin.objects.filter(pk=admin_id).first()
    if not admin:
        return render(request, 'admin/reset_password.html', {'invalid': True})

    if request.method == 'POST':
        new_pw = request.POST.get('new_password', '')
        confirm_pw = request.POST.get('confirm_password', '')

        if len(new_pw) < 6:
            return render(request, 'admin/reset_password.html', {
                'token': token, 'error': 'Password must be at least 6 characters.'
            })
        if new_pw != confirm_pw:
            return render(request, 'admin/reset_password.html', {
                'token': token, 'error': 'Passwords do not match.'
            })

        from django.contrib.auth.hashers import make_password as django_make
        admin.password = django_make(new_pw)
        admin.save(update_fields=['password'])
        # Invalidate token after use
        _admin_reset_tokens.pop(token, None)
        return render(request, 'admin/reset_password.html', {'success': True})

    return render(request, 'admin/reset_password.html', {'token': token})
