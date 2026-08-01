from decimal import Decimal
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


# Admin model for custom admin panel
class Admin(models.Model):
    admin_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=256)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


# Customer model — main user account
class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=256)  # stores hashed password
    address = models.CharField(max_length=255)
    reg_date = models.DateField(auto_now_add=True)
    # Extended profile fields
    gender = models.CharField(max_length=10, blank=True, default='')
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        # Guard: guest accounts have empty passwords — never allow login
        if not self.password:
            return False
        # Support legacy plain-text passwords (auto-upgrade on first login)
        if not self.password.startswith(('pbkdf2_', 'bcrypt', 'argon2', '!')):
            if self.password == raw_password:
                self.set_password(raw_password)
                self.save(update_fields=['password'])
                return True
            return False
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.name


# Car_Brand
class CarBrand(models.Model):
    brand_id = models.AutoField(primary_key=True)
    brand_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.brand_name


#  Car_Model
class CarModel(models.Model):
    model_id = models.AutoField(primary_key=True)
    brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=50)
    base_color = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # One neutral/base photo per model; tint in UI using CarColor.color_code
    preview_image = models.ImageField(
        upload_to="car_models/",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.model_name


#  Customization
class Customization(models.Model):
    customization_id = models.AutoField(primary_key=True)
    model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    color_option = models.CharField(max_length=30)
    preview_image = models.CharField(max_length=255, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.color_option} - {self.model}"


#  Service
class Service(models.Model):
    service_id = models.AutoField(primary_key=True)
    service_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.service_name


#  Booking
class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    booking_date = models.DateField(auto_now_add=True)
    schedule_date = models.DateField()
    status = models.CharField(max_length=20, default="Pending")

    def __str__(self):
        return f"Booking {self.booking_id}"


#  Payment
class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="Success")

    def __str__(self):
        return f"Payment {self.payment_id}"


# Feedback
class Feedback(models.Model):
    feedback_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    message = models.TextField()
    rating = models.IntegerField()
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Feedback {self.feedback_id}"
    
# CarColor
class CarColor(models.Model):
    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    color_name = models.CharField(max_length=50)
    color_code = models.CharField(max_length=7)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_quantity = models.IntegerField(default=0)

    def __str__(self):
        return self.color_name


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE)
    model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    color = models.ForeignKey(CarColor, on_delete=models.CASCADE)
    services = models.ManyToManyField(Service, blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"Order {self.order_id} - {self.customer.name}"

class Customers(models.Model):
    """Legacy model — kept for migration compatibility only. Use Customer instead."""
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    password = models.CharField(max_length=256)
    address = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

# CartItem — one row per color item added to cart by a customer
# class CartItem(models.Model):
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
#     color = models.ForeignKey(CarColor, on_delete=models.CASCADE)
#     quantity = models.IntegerField(default=1)

#     def __str__(self):
#         return f"Cart: {self.customer.name} - {self.color.color_name}"
class CartItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('color', 'Color Product'),
        ('service', 'Service'),
        ('custom', 'Custom Car'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='color')

    # For color items
    color = models.ForeignKey(CarColor, on_delete=models.SET_NULL, null=True, blank=True)

    # For service items
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)

    # For custom car items
    custom_config = models.JSONField(null=True, blank=True)

    quantity = models.IntegerField(default=1)

    def get_price(self):
       from decimal import Decimal
       if self.item_type == 'color' and self.color:
        return self.color.price
       elif self.item_type == 'service' and self.service:
        return self.service.price
       elif self.item_type == 'custom' and self.custom_config:
        return Decimal(str(self.custom_config.get('price', 0)))
       return Decimal('0')

    def get_label(self):
        if self.item_type == 'color' and self.color:
            return f"{self.color.color_name} — {self.color.car_model.brand.brand_name} {self.color.car_model.model_name}"
        elif self.item_type == 'service' and self.service:
            return self.service.service_name
        elif self.item_type == 'custom' and self.custom_config:
            return f"Custom Car — {self.custom_config.get('brand')} {self.custom_config.get('model')} ({self.custom_config.get('color')})"
        return "Cart Item"

    def __str__(self):
        return self.get_label()


# SavedCustomization — lets logged-in users save their color picks
class SavedCustomization(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='saved_customizations')
    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    color = models.ForeignKey(CarColor, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'car_model', 'color')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.customer.name} — {self.car_model.model_name} ({self.color.color_name})"


# RecentlyViewed — tracks which models a customer has viewed
class RecentlyViewed(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='recently_viewed')
    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('customer', 'car_model')
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.customer.name} viewed {self.car_model.model_name}"


# UserFeedback — simple public feedback form (no login required)
class UserFeedback(models.Model):
    name = models.CharField(max_length=100)
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Feedback from {self.name}"
