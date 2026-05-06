# Printer Hub - Setup Guide (Windows)

This guide is for running the project on another PC.

## 1) Minimum Hardware Requirements

- CPU: Dual-core processor (Intel i3/Ryzen 3 or better recommended)
- RAM: 4 GB minimum, 8 GB recommended
- Disk Space: 2 GB free minimum
- Internet: Required for first-time package installation

## 2) Software to Install

Install these in order:

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

Then open in browser:

- App: http://127.0.0.1:8000
- Admin: http://127.0.0.1:8000/admin

## 5) Daily Run Commands

Every time you want to start the app:

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

If server says port is busy, run on another port:

```powershell
python manage.py runserver 8001
```

### Database issues

Re-apply migrations:

```powershell
python manage.py migrate
```

### Static/media notes

- Static files are configured from `core/static`
- Media uploads are served in development mode

---

If needed, share this entire file with your brother and ask him to follow section 4 exactly for first run.
