# Printer Hub - Setup Guide (Windows)

This guide explains how to run the project on another Windows PC.

## 1) Minimum Hardware Requirements

- CPU: Dual-core processor (Intel i3/Ryzen 3 or better recommended)
- RAM: 4 GB minimum, 8 GB recommended
- Disk Space: 2 GB free minimum
- Internet: Required for first-time package installation

## 2) Software to Install

Install the following in order:

1. Python 3.12 (or newer)
2. Git (recommended)
3. Visual Studio Code (recommended)

Notes:
- SQLite database support is built into Python, so no separate SQLite install is needed.
- This project uses Django and Pillow (image handling).

## 3) Verify Installations

Open PowerShell and run:

```powershell
python --version
pip --version
git --version
```

If `python` does not work, try:

```powershell
py --version
```

## 4) Project Setup (First Time)

Open PowerShell in the project folder (`printerhub`) and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install Django==6.0.4 Pillow
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open these URLs in your browser:

- App: http://127.0.0.1:8000
- Admin: http://127.0.0.1:8000/admin

## 5) Daily Run Commands

Use these commands each time you want to start the app:

```powershell
cd <path-to-printerhub>
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

## 6) If PowerShell Blocks Virtual Environment Activation

Run PowerShell as Administrator and execute:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Close and reopen PowerShell, then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 7) Optional: Save Dependencies for Easy Reinstall

From activated venv:

```powershell
pip freeze > requirements.txt
```

On another PC:

```powershell
pip install -r requirements.txt
```

## 8) Common Fixes

### Port already in use

If the server says the port is busy, run on another port:

```powershell
python manage.py runserver 8001
```

### Database issues

Re-apply migrations:

```powershell
python manage.py migrate
```

### Static and media notes

- Static files are configured from `core/static`.
- Media uploads are served in development mode

## 9) Email OTP Setup (Free)

This project now supports email OTP for signup and login.

By default, OTP emails are printed in the terminal (console backend), so no SMTP setup is required for local testing.

To send real OTP emails for free, use a Gmail account with an App Password:

1. Enable 2-Step Verification on your Gmail account.
2. Generate an App Password from Google account security settings.
3. Set these environment variables before running `python manage.py runserver`:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "smtp.gmail.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_USE_TLS = "True"
$env:EMAIL_HOST_USER = "yourgmail@gmail.com"
$env:EMAIL_HOST_PASSWORD = "your_app_password"
$env:DEFAULT_FROM_EMAIL = "Printer Hub <yourgmail@gmail.com>"
```

Then run the server and OTP emails will be delivered to user inbox.

## 10) Payment Flow Note

The payment page supports UPI, card, and net banking selection for a real-project style flow.
It currently stores payment method and reference in the order for demonstration.

For production, connect a real gateway (recommended: Razorpay test mode first, then live keys).

---

If needed, share this entire file with your brother and ask him to follow Section 4 exactly for the first run.
