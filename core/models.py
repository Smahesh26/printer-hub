from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    USER_TYPE = (
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPE)

    def __str__(self):
        return self.user.username


class Printer(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    type = models.CharField(
        max_length=10,
        choices=[('sale', 'Sale'), ('rent', 'Rent')]
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='printers/')
    payment_qr = models.ImageField(upload_to='payment_qr/', blank=True, null=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    PAYMENT_METHODS = (
        ('upi', 'UPI'),
        ('card', 'Credit/Debit Card'),
        ('netbanking', 'Net Banking'),
    )
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    )

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, related_name='orders')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='upi')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='paid')
    payment_reference = models.CharField(max_length=64, blank=True)
    ordered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ordered_at']

    def __str__(self):
        return f"Order #{self.id} - {self.buyer.username} - {self.printer.name}"


class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_chat_messages')
    printer = models.ForeignKey(Printer, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"


class EmailOTP(models.Model):
    PURPOSES = (
        ('signup', 'Signup Verification'),
        ('login', 'Login Verification'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField()
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self, submitted_code):
        return (
            not self.is_used
            and self.code == submitted_code
            and timezone.now() <= self.expires_at
        )

    def __str__(self):
        return f"{self.email} ({self.purpose})"