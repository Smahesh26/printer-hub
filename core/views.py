from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal, InvalidOperation
from datetime import timedelta
import random
import razorpay

from .models import Profile, Printer, Order, ChatMessage, EmailOTP
from .decorators import buyer_required, seller_required


OTP_EXPIRY_MINUTES = 10


def _generate_otp_code():
    return f"{random.randint(100000, 999999)}"


def _send_otp_email(email, code, purpose):
    purpose_label = 'login' if purpose == 'login' else 'signup'
    subject = f'Printer Hub OTP for {purpose_label}'
    message = (
        f'Your Printer Hub OTP is: {code}\n\n'
        f'This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.\n'
        'Do not share this code with anyone.'
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@printerhub.local')
    send_mail(subject, message, from_email, [email], fail_silently=False)


def _create_and_send_otp(*, email, purpose, user=None):
    code = _generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    otp = EmailOTP.objects.create(
        user=user,
        email=email,
        purpose=purpose,
        code=code,
        expires_at=expires_at,
    )
    _send_otp_email(email, code, purpose)
    return otp


def _verify_otp(*, email, purpose, submitted_code, user=None):
    otp_qs = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        is_used=False,
    )
    if user is not None:
        otp_qs = otp_qs.filter(user=user)

    otp = otp_qs.order_by('-created_at').first()
    if not otp:
        return False

    if not otp.is_valid(submitted_code):
        return False

    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return True


def _razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


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

        if not username or not email or not password:
            error = 'Username, email, and password are required.'
        elif User.objects.filter(email__iexact=email).exists():
            error = 'Email already registered. Please use another email.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif User.objects.filter(username__iexact=username).exists():
            error = 'Username already taken. Please choose another.'
        else:
            try:
                _create_and_send_otp(email=email, purpose='signup')
            except Exception:
                error = 'Unable to send OTP email right now. Please try again.'
            else:
                request.session['pending_signup'] = {
                    'username': username,
                    'email': email,
                    'password': password,
                    'user_type': form_data['user_type'],
                }
                return redirect('verify_signup_otp')

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
            if not user.email:
                error = 'Your account has no email. Contact admin to add email for OTP login.'
            else:
                try:
                    _create_and_send_otp(email=user.email, purpose='login', user=user)
                except Exception:
                    error = 'Unable to send OTP email right now. Please try again.'
                else:
                    request.session['pending_login_user_id'] = user.id
                    return redirect('verify_login_otp')
        else:
            error = 'Invalid username or password.'

    return render(request, 'login.html', {'error': error})


# Logout
def logout_view(request):
    logout(request)
    return redirect('home')


def verify_signup_otp(request):
    pending_signup = request.session.get('pending_signup')
    if not pending_signup:
        messages.warning(request, 'Signup session expired. Please register again.')
        return redirect('signup')

    error = None
    if request.method == 'POST':
        code = request.POST.get('otp', '').strip()
        if not code:
            error = 'Please enter the OTP sent to your email.'
        else:
            is_valid = _verify_otp(
                email=pending_signup['email'],
                purpose='signup',
                submitted_code=code,
            )
            if not is_valid:
                error = 'Invalid or expired OTP. Please try again.'
            else:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=pending_signup['username'],
                            email=pending_signup['email'],
                            password=pending_signup['password'],
                        )
                        Profile.objects.create(user=user, user_type=pending_signup['user_type'])
                except IntegrityError:
                    error = 'Username or email already exists. Please sign up again.'
                else:
                    request.session.pop('pending_signup', None)
                    login(request, user)
                    return _redirect_by_role(user)

    return render(request, 'verify_otp.html', {
        'title': 'Verify Signup OTP',
        'subtitle': f"Enter the OTP sent to {pending_signup['email']}",
        'error': error,
        'resend_url': '/otp/resend-signup/',
    })


def resend_signup_otp(request):
    pending_signup = request.session.get('pending_signup')
    if not pending_signup:
        messages.warning(request, 'Signup session expired. Please register again.')
        return redirect('signup')

    try:
        _create_and_send_otp(email=pending_signup['email'], purpose='signup')
    except Exception:
        messages.error(request, 'Unable to resend OTP right now. Please try again.')
    else:
        messages.success(request, 'A new OTP has been sent to your email.')
    return redirect('verify_signup_otp')


def verify_login_otp(request):
    pending_user_id = request.session.get('pending_login_user_id')
    if not pending_user_id:
        messages.warning(request, 'Login session expired. Please login again.')
        return redirect('login')

    user = User.objects.filter(id=pending_user_id).first()
    if not user or not user.email:
        request.session.pop('pending_login_user_id', None)
        messages.warning(request, 'Login session is invalid. Please login again.')
        return redirect('login')

    error = None
    if request.method == 'POST':
        code = request.POST.get('otp', '').strip()
        if not code:
            error = 'Please enter the OTP sent to your email.'
        else:
            is_valid = _verify_otp(
                email=user.email,
                purpose='login',
                submitted_code=code,
                user=user,
            )
            if not is_valid:
                error = 'Invalid or expired OTP. Please try again.'
            else:
                request.session.pop('pending_login_user_id', None)
                login(request, user)
                return _redirect_by_role(user)

    return render(request, 'verify_otp.html', {
        'title': 'Verify Login OTP',
        'subtitle': f"Enter the OTP sent to {user.email}",
        'error': error,
        'resend_url': '/otp/resend-login/',
    })


def resend_login_otp(request):
    pending_user_id = request.session.get('pending_login_user_id')
    if not pending_user_id:
        messages.warning(request, 'Login session expired. Please login again.')
        return redirect('login')

    user = User.objects.filter(id=pending_user_id).first()
    if not user or not user.email:
        request.session.pop('pending_login_user_id', None)
        messages.warning(request, 'Login session is invalid. Please login again.')
        return redirect('login')

    try:
        _create_and_send_otp(email=user.email, purpose='login', user=user)
    except Exception:
        messages.error(request, 'Unable to resend OTP right now. Please try again.')
    else:
        messages.success(request, 'A new OTP has been sent to your email.')
    return redirect('verify_login_otp')


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
        Printer.objects.create(
            seller=request.user,
            name=request.POST['name'],
            model=request.POST['model'],
            type=request.POST['type'],
            price=request.POST['price'],
            image=request.FILES['image'],
        )
        messages.success(request, 'Printer added successfully.')
        return redirect('seller_dashboard')

    return render(request, 'add_printer.html')


# Payment page (Buyer only)
@buyer_required
def pay_order(request, printer_id):
    printer = get_object_or_404(Printer, id=printer_id)
    payment_methods = [
        ('upi', 'UPI'),
        ('card', 'Credit / Debit Card'),
        ('netbanking', 'Net Banking'),
    ]

    amount_paise = int(printer.price * Decimal('100'))
    receipt_id = f"ph-{request.user.id}-{printer.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    razorpay_order = None

    try:
        client = _razorpay_client()
        razorpay_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt_id,
            'payment_capture': 1,
            'notes': {
                'buyer_id': str(request.user.id),
                'printer_id': str(printer.id),
            },
        })
    except Exception:
        messages.error(request, 'Unable to initialize Razorpay payment right now. Please try again.')

    return render(request, 'payment.html', {
        'printer': printer,
        'payment_methods': payment_methods,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': razorpay_order['id'] if razorpay_order else '',
        'razorpay_callback_url': request.build_absolute_uri(
            reverse('verify_razorpay_payment', args=[printer.id])
        ),
        'amount_paise': amount_paise,
        'buyer_name': request.user.get_full_name() or request.user.username,
        'buyer_email': request.user.email,
    })


@csrf_exempt
def verify_razorpay_payment(request, printer_id):
    if request.method != 'POST':
        return redirect('pay_order', printer_id=printer_id)

    printer = get_object_or_404(Printer, id=printer_id)
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()

    if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
        messages.error(request, 'Payment verification data is incomplete. Please try again.')
        return redirect('pay_order', printer_id=printer.id)

    try:
        client = _razorpay_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except Exception:
        messages.error(request, 'Razorpay payment verification failed. Please try again.')
        return redirect('pay_order', printer_id=printer.id)

    razorpay_order = None
    try:
        razorpay_order = client.order.fetch(razorpay_order_id)
    except Exception:
        messages.error(request, 'Unable to fetch Razorpay order details. Please try again.')
        return redirect('pay_order', printer_id=printer.id)

    notes = razorpay_order.get('notes', {}) if isinstance(razorpay_order, dict) else {}
    buyer_id = notes.get('buyer_id')
    noted_printer_id = notes.get('printer_id')
    if str(noted_printer_id) != str(printer.id):
        messages.error(request, 'Payment details do not match this printer.')
        return redirect('dashboard')

    buyer = User.objects.filter(id=buyer_id).first()
    if not buyer:
        messages.error(request, 'Unable to resolve buyer account for this payment.')
        return redirect('login')

    existing_order = Order.objects.filter(
        buyer=buyer,
        printer=printer,
        payment_reference=razorpay_payment_id,
    ).first()
    if existing_order:
        if request.user.is_authenticated and request.user.id == buyer.id:
            return redirect('order_confirmation', order_id=existing_order.id)
        return redirect('/dashboard/?tab=orders')

    payment_method = 'upi'
    payment_status = 'paid'
    try:
        payment_data = client.payment.fetch(razorpay_payment_id)
        method_map = {
            'upi': 'upi',
            'card': 'card',
            'netbanking': 'netbanking',
        }
        payment_method = method_map.get(payment_data.get('method', ''), 'upi')
        gateway_status = payment_data.get('status', '').lower()
        if gateway_status and gateway_status not in {'captured', 'authorized'}:
            payment_status = 'pending'
    except Exception:
        # Keep fallback values when payment fetch is unavailable.
        pass

    order = Order.objects.create(
        buyer=buyer,
        printer=printer,
        payment_method=payment_method,
        payment_status=payment_status,
        payment_reference=razorpay_payment_id,
    )
    if request.user.is_authenticated and request.user.id == buyer.id:
        return redirect('order_confirmation', order_id=order.id)
    return redirect('/dashboard/?tab=orders')


# Create order (Buyer only)
@buyer_required
def create_order(request, printer_id):
    if request.method != 'POST':
        return redirect('dashboard')

    printer = get_object_or_404(Printer, id=printer_id)
    order = Order.objects.create(
        buyer=request.user,
        printer=printer,
        payment_method='upi',
        payment_status='paid',
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