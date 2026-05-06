from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from .models import Profile, Printer, Order, ChatMessage
from .decorators import buyer_required, seller_required


# Home page
def home(request):
    printers = Printer.objects.all()
    return render(request, 'home.html', {'printers': printers})


# About page
def about(request):
    return render(request, 'about.html')


# Contact page
def contact(request):
    return render(request, 'contact.html')


# Public printers listing
def printers_list(request):
    printers = Printer.objects.select_related('seller').all()

    q = request.GET.get('q', '').strip()
    listing_type = request.GET.get('type', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    if q:
        printers = printers.filter(Q(name__icontains=q) | Q(model__icontains=q))
    if listing_type in ('sale', 'rent'):
        printers = printers.filter(type=listing_type)
    if min_price:
        try:
            printers = printers.filter(price__gte=Decimal(min_price))
        except (InvalidOperation, ValueError):
            min_price = ''
    if max_price:
        try:
            printers = printers.filter(price__lte=Decimal(max_price))
        except (InvalidOperation, ValueError):
            max_price = ''

    return render(request, 'printers.html', {
        'printers': printers,
        'q': q,
        'type': listing_type,
        'min_price': min_price,
        'max_price': max_price,
    })


# Signup
def signup(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    error = None
    form_data = {
        'username': '',
        'email': '',
        'user_type': 'buyer',
    }

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        user_type = request.POST.get('user_type', 'buyer')

        form_data = {
            'username': username,
            'email': email,
            'user_type': user_type if user_type in ('buyer', 'seller') else 'buyer',
        }

        if not username or not password:
            error = 'Username and password are required.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif User.objects.filter(username__iexact=username).exists():
            error = 'Username already taken. Please choose another.'
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                    )
                    Profile.objects.create(user=user, user_type=form_data['user_type'])
            except IntegrityError:
                error = 'Username already taken. Please choose another.'
            else:
                login(request, user)
                return _redirect_by_role(user)

    return render(request, 'signup.html', {'error': error, 'form_data': form_data})


# Login
def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return _redirect_by_role(user)
        else:
            error = 'Invalid username or password.'

    return render(request, 'login.html', {'error': error})


# Logout
def logout_view(request):
    logout(request)
    return redirect('home')


# Helper: redirect after login based on role
def _redirect_by_role(user):
    try:
        if user.profile.user_type == 'seller':
            return redirect('seller_dashboard')
    except Profile.DoesNotExist:
        pass
    return redirect('dashboard')


def _user_type(user):
    try:
        return user.profile.user_type
    except Profile.DoesNotExist:
        return ''


# Buyer dashboard
@buyer_required
def dashboard(request):
    tab = request.GET.get('tab', 'browse').strip() or 'browse'

    if request.method == 'POST' and request.POST.get('form_type') == 'profile':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('/dashboard/?tab=profile')

    printers = Printer.objects.all()

    search_query = request.GET.get('q', '').strip()
    listing_type = request.GET.get('type', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    if search_query:
        printers = printers.filter(
            Q(name__icontains=search_query) | Q(model__icontains=search_query)
        )

    if listing_type in ('sale', 'rent'):
        printers = printers.filter(type=listing_type)

    if min_price:
        try:
            min_price_decimal = Decimal(min_price)
            printers = printers.filter(price__gte=min_price_decimal)
        except (InvalidOperation, ValueError):
            min_price = ''

    if max_price:
        try:
            max_price_decimal = Decimal(max_price)
            printers = printers.filter(price__lte=max_price_decimal)
        except (InvalidOperation, ValueError):
            max_price = ''

    context = {
        'printers': printers,
        'orders': Order.objects.filter(buyer=request.user).select_related('printer'),
        'q': search_query,
        'type': listing_type,
        'min_price': min_price,
        'max_price': max_price,
        'tab': tab,
    }
    return render(request, 'dashboard.html', context)


# Seller dashboard
@seller_required
def seller_dashboard(request):
    printers = Printer.objects.filter(seller=request.user)
    seller_orders = Order.objects.filter(
        printer__seller=request.user
    ).select_related('buyer', 'printer')
    return render(request, 'seller_dashboard.html', {
        'printers': printers,
        'seller_orders': seller_orders,
    })


# Add printer (Seller only)
@seller_required
def add_printer(request):
    if request.method == 'POST':
        payment_qr = request.FILES.get('payment_qr')
        if not payment_qr:
            messages.error(request, 'Please upload your payment QR code for this listing.')
            return render(request, 'add_printer.html')

        Printer.objects.create(
            seller=request.user,
            name=request.POST['name'],
            model=request.POST['model'],
            type=request.POST['type'],
            price=request.POST['price'],
            image=request.FILES['image'],
            payment_qr=payment_qr,
        )
        messages.success(request, 'Printer added successfully.')
        return redirect('seller_dashboard')

    return render(request, 'add_printer.html')


# Payment page (Buyer only) — shows UPI QR before confirming order
@buyer_required
def pay_order(request, printer_id):
    printer = get_object_or_404(Printer, id=printer_id)
    if not printer.payment_qr:
        messages.error(request, 'Seller QR code is not available for this printer yet.')
        return redirect('dashboard')

    if request.method == 'POST':
        order = Order.objects.create(buyer=request.user, printer=printer)
        return redirect('order_confirmation', order_id=order.id)
    return render(request, 'payment.html', {'printer': printer})


# Create order (Buyer only)
@buyer_required
def create_order(request, printer_id):
    if request.method != 'POST':
        return redirect('dashboard')

    printer = get_object_or_404(Printer, id=printer_id)
    order = Order.objects.create(
        buyer=request.user,
        printer=printer,
    )
    return redirect('order_confirmation', order_id=order.id)


# Order confirmation (Buyer only)
@buyer_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    return render(request, 'order_confirmation.html', {'order': order})


@login_required(login_url='/login/')
def inbox(request):
    all_messages = ChatMessage.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).select_related('sender', 'receiver').order_by('-created_at')

    conversations = {}
    for item in all_messages:
        other_user = item.receiver if item.sender_id == request.user.id else item.sender
        if other_user.id not in conversations:
            conversations[other_user.id] = {
                'user': other_user,
                'last_message': item,
                'unread_count': 0,
            }

        if item.receiver_id == request.user.id and not item.is_read:
            conversations[other_user.id]['unread_count'] += 1

    back_url = '/dashboard/'
    if _user_type(request.user) == 'seller':
        back_url = '/seller/'

    context = {
        'conversations': list(conversations.values()),
        'back_url': back_url,
    }
    return render(request, 'inbox.html', context)


@login_required(login_url='/login/')
def chat_room(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user.id == request.user.id:
        return redirect('inbox')

    current_role = _user_type(request.user)
    other_role = _user_type(other_user)
    if current_role == other_role or not current_role or not other_role:
        messages.warning(request, 'You are not authorized to start this chat.')
        return redirect('inbox')

    selected_printer = None
    printer_id = request.GET.get('printer', '').strip() or request.POST.get('printer_id', '').strip()
    if printer_id and current_role == 'buyer':
        selected_printer = Printer.objects.filter(id=printer_id, seller=other_user).first()

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            ChatMessage.objects.create(
                sender=request.user,
                receiver=other_user,
                printer=selected_printer,
                body=body,
            )
            return redirect('chat_room', user_id=other_user.id)

    chat_messages = ChatMessage.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).select_related('sender', 'receiver', 'printer')

    ChatMessage.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False,
    ).update(is_read=True)

    if not selected_printer:
        last_reference = chat_messages.filter(printer__isnull=False).last()
        if last_reference:
            selected_printer = last_reference.printer

    context = {
        'other_user': other_user,
        'chat_messages': chat_messages,
        'selected_printer': selected_printer,
    }
    return render(request, 'chat_room.html', context)