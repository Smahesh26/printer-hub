from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Profile, Printer, Order, ChatMessage


class ProfileInline(admin.StackedInline):
	model = Profile
	can_delete = True
	extra = 0


class CustomUserAdmin(UserAdmin):
	inlines = [ProfileInline]
	list_display = ('username', 'email', 'user_type', 'is_staff', 'is_active', 'date_joined')
	list_filter = ('is_staff', 'is_active', 'is_superuser', 'groups', 'profile__user_type')
	search_fields = ('username', 'email', 'first_name', 'last_name')
	ordering = ('-date_joined',)
	actions = ('set_as_buyer', 'set_as_seller')

	@admin.display(description='Role')
	def user_type(self, obj):
		try:
			return obj.profile.get_user_type_display()
		except Profile.DoesNotExist:
			return 'No Profile'

	@admin.action(description='Set selected users as Buyer')
	def set_as_buyer(self, request, queryset):
		updated_count = 0
		for user in queryset:
			Profile.objects.update_or_create(user=user, defaults={'user_type': 'buyer'})
			updated_count += 1
		self.message_user(request, f'{updated_count} user(s) updated as Buyer.')

	@admin.action(description='Set selected users as Seller')
	def set_as_seller(self, request, queryset):
		updated_count = 0
		for user in queryset:
			Profile.objects.update_or_create(user=user, defaults={'user_type': 'seller'})
			updated_count += 1
		self.message_user(request, f'{updated_count} user(s) updated as Seller.')


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'user_type')
	list_filter = ('user_type',)
	search_fields = ('user__username', 'user__email')


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
	list_display = ('name', 'model', 'type', 'price', 'seller', 'payment_qr')
	list_filter = ('type',)
	search_fields = ('name', 'model', 'seller__username')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('id', 'buyer', 'printer', 'ordered_at')
	list_filter = ('ordered_at',)
	search_fields = ('buyer__username', 'printer__name')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
	list_display = ('sender', 'receiver', 'printer', 'is_read', 'created_at')
	list_filter = ('is_read', 'created_at')
	search_fields = ('sender__username', 'receiver__username', 'body')
