from django.contrib import admin
from .models import (
    Admin, Customer, Customers, CarBrand, CarModel, CarColor,
    Customization, Service, Booking, Payment, Feedback,
    CartItem, Order, SavedCustomization, RecentlyViewed, UserFeedback,
)


@admin.register(CarBrand)
class CarBrandAdmin(admin.ModelAdmin):
    list_display = ('brand_id', 'brand_name')
    search_fields = ('brand_name',)


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('model_id', 'model_name', 'brand', 'price', 'base_color')
    list_filter = ('brand',)
    search_fields = ('model_name', 'brand__brand_name')


@admin.register(CarColor)
class CarColorAdmin(admin.ModelAdmin):
    list_display = ('car_model', 'color_name', 'color_code', 'price', 'stock_quantity')
    search_fields = ('car_model__model_name', 'color_name', 'color_code')
    list_filter = ('car_model__brand', 'car_model')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_id', 'service_name', 'price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('service_name',)
    list_editable = ('is_active',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'customer', 'brand', 'model', 'color', 'total_price', 'status', 'order_date')
    list_filter = ('status', 'brand', 'order_date')
    search_fields = ('customer__name', 'customer__email', 'model__model_name')
    list_editable = ('status',)


@admin.register(Customization)
class CustomizationAdmin(admin.ModelAdmin):
    list_display = ('customization_id', 'customer', 'model', 'color_option', 'date')
    list_filter = ('model', 'date')
    search_fields = ('customer__name', 'model__model_name', 'color_option')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'name', 'email', 'phone', 'reg_date')
    search_fields = ('name', 'email', 'phone')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'customer', 'service', 'schedule_date', 'status')
    list_filter = ('status', 'service')


admin.site.register(Admin)
admin.site.register(Payment)
admin.site.register(CartItem)
admin.site.register(SavedCustomization)
admin.site.register(RecentlyViewed)
admin.site.register(Customers)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display  = ('feedback_id', 'customer', 'rating', 'date')
    list_filter   = ('rating', 'date')
    search_fields = ('customer__name',)
    readonly_fields = ('feedback_id', 'customer', 'message', 'rating', 'date')


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display    = ('id', 'name', 'short_message', 'submitted_at')
    search_fields   = ('name', 'message')
    readonly_fields = ('name', 'message', 'submitted_at')
    ordering        = ('-submitted_at',)

    @admin.display(description='Message')
    def short_message(self, obj):
        return obj.message[:80] + '…' if len(obj.message) > 80 else obj.message
