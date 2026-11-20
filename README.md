# Anda Tayo

Find a hangout or study spot in Zamboanga City that fits your mood.
Django + MySQL (XAMPP) + Tailwind CSS + Leaflet/OpenStreetMap.

## Quick start (Windows)

You need **Python** (with "Add python.exe to PATH" ticked) and **XAMPP**.

1. Open the **XAMPP Control Panel** and click **Start** next to **MySQL**.
2. Clone the repo:
   ```
   git clone https://github.com/brtlm-ui/ANDA-TAYO.git
   ```
3. Open the `ANDA-TAYO` folder and **double-click `setup.bat`**.
   It creates the `venv`, installs the packages, creates the `andatayo_db` database,
   runs the migrations, loads the demo spots + photos, asks if you want an admin login,
   and starts the site.
4. Open http://127.0.0.1:8000/

**Every day after that:** start MySQL in XAMPP, then double-click **`run.bat`**.
It also applies any new migrations after you `git pull`.

| Page | URL |
|------|-----|
| Discover (home) | http://127.0.0.1:8000/ |
| Browse spots | http://127.0.0.1:8000/spots/ |
| Map explorer | http://127.0.0.1:8000/map/ |
| Admin | http://127.0.0.1:8000/admin/ |

## Manual setup (same thing, step by step)

From the repo folder, with MySQL running in XAMPP:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
C:\xampp\mysql\bin\mysql.exe -u root -e "CREATE DATABASE IF NOT EXISTS andatayo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cd AndaTayo
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

## Notes

- Database settings are in `AndaTayo/AndaTayo/settings.py` (`andatayo_db`, user `root`, no password,
  port 3306 — the XAMPP defaults). If your MySQL root has a password, put it in `PASSWORD`.
- Each person has their own local database. Data you add on your machine (spots, reviews, admin
  accounts) is **not** shared through GitHub — only the code and migrations are.
- Uploaded photos go to `AndaTayo/media/` (not committed). The demo photos are restored by
  `python manage.py seed_demo`.
- Run the tests: `cd AndaTayo` then `python manage.py test core`
