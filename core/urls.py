from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('printers/', views.printers_list, name='printers_list'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('signup/', views.signup, name='signup'),
    path('signup/verify-otp/', views.verify_signup_otp, name='verify_signup_otp'),
    path('login/', views.login_view, name='login'),
    path('login/verify-otp/', views.verify_login_otp, name='verify_login_otp'),
    path('otp/resend-signup/', views.resend_signup_otp, name='resend_signup_otp'),
    path('otp/resend-login/', views.resend_login_otp, name='resend_login_otp'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('seller/', views.seller_dashboard, name='seller_dashboard'),
    path('add/', views.add_printer, name='add_printer'),
    path('order/pay/<int:printer_id>/', views.pay_order, name='pay_order'),
    path('order/pay/<int:printer_id>/verify/', views.verify_razorpay_payment, name='verify_razorpay_payment'),
    path('order/create/<int:printer_id>/', views.create_order, name='create_order'),
    path('order/confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('inbox/', views.inbox, name='inbox'),
    path('chat/<int:user_id>/', views.chat_room, name='chat_room'),
]