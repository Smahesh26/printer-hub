from django.db import models
from django.contrib.auth.models import User


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

    def __str__(self):
        return self.name


class Order(models.Model):
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, related_name='orders')
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