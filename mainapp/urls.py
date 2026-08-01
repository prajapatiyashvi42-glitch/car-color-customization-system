from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),

    # Auth
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # Browse
    path('brands/', views.brands, name='brands'),
    path('models/<int:brand_id>/', views.models, name='models'),
    path('select-model/', views.brand_model_selector, name='brand_model_selector'),
    path('api/models/<int:brand_id>/', views.models_by_brand, name='models_by_brand_api'),
    path('customize/<int:model_id>/', views.customize, name='customize'),
    path('car-colors/', views.car_colors, name='car_colors'),

    # Customization save
    path('save-customization/', views.save_customization, name='save_customization'),

    # Services
    path('services/', views.services, name='services'),
    path('book-service/<int:service_id>/', views.book_service, name='book_service'),

    # Feedback
    path('feedback/', views.feedback, name='feedback'),

    # Cart
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),
    path('cart/payment-confirm/', views.cart_payment_confirm, name='cart_payment_confirm'),

    # Direct order
    path('order/', views.order, name='order'),
    path('payment-confirm/', views.payment_confirm, name='payment_confirm'),

    # User — My Orders
    path('my-orders/', views.my_orders, name='my_orders'),
    path('my-orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),

    # ── Custom Admin Panel ──
    path('admin-panel/login/', views.admin_login, name='admin_login'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/analytics/', views.admin_analytics, name='admin_analytics'),

    # Colors
    path('admin-panel/colors/', views.admin_colors, name='admin_colors'),
    path('admin-panel/colors/add/', views.admin_color_create, name='admin_color_add'),
    path('admin-panel/colors/<int:color_id>/edit/', views.admin_color_edit, name='admin_color_edit'),
    path('admin-panel/colors/<int:color_id>/delete/', views.admin_color_delete, name='admin_color_delete'),

    # Brands
    path('admin-panel/brands/', views.admin_brands, name='admin_brands'),
    path('admin-panel/brands/add/', views.admin_brand_create, name='admin_brand_add'),
    path('admin-panel/brands/<int:brand_id>/edit/', views.admin_brand_edit, name='admin_brand_edit'),
    path('admin-panel/brands/<int:brand_id>/delete/', views.admin_brand_delete, name='admin_brand_delete'),

    # Car Models
    path('admin-panel/car-models/', views.admin_car_models, name='admin_car_models'),
    path('admin-panel/car-models/add/', views.admin_car_model_create, name='admin_car_model_add'),
    path('admin-panel/car-models/<int:model_id>/edit/', views.admin_car_model_edit, name='admin_car_model_edit'),
    path('admin-panel/car-models/<int:model_id>/delete/', views.admin_car_model_delete, name='admin_car_model_delete'),

    # Services
    path('admin-panel/services/', views.admin_services, name='admin_services'),
    path('admin-panel/services/add/', views.admin_service_create, name='admin_service_add'),
    path('admin-panel/services/<int:service_id>/edit/', views.admin_service_edit, name='admin_service_edit'),
    path('admin-panel/services/<int:service_id>/delete/', views.admin_service_delete, name='admin_service_delete'),

    # Customizations
    path('admin-panel/customizations/', views.admin_customizations, name='admin_customizations'),
    path('admin-panel/customizations/<int:cust_id>/delete/', views.admin_customization_delete, name='admin_customization_delete'),

    # Orders
    path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
    path('admin-panel/orders/<int:order_id>/status/', views.admin_order_status_update, name='admin_order_status_update'),

    # Report
    path('admin-panel/generate-report/', views.generate_report, name='generate_report'),

    # Admin password management
    path('admin-panel/change-password/', views.admin_change_password, name='admin_change_password'),
    path('admin-panel/forgot-password/', views.admin_forgot_password, name='admin_forgot_password'),
    path('admin-panel/reset-password/<str:token>/', views.admin_reset_password, name='admin_reset_password'),

    # Customer change password
    path('change-password/', views.customer_change_password, name='customer_change_password'),
]
