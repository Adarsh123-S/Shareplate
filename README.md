# 🍱 SharePlate — Community Food Sharing Platform

> **Share Food. Reduce Waste. Feed Hope.**

SharePlate connects people with surplus food to those who need it. Zero waste. Real impact.

---

## 🚀 Features

- **User Auth** — Register, Login, Logout with hashed passwords
- **Donate Food** — Post food with name, category, quantity, location, expiry
- **Browse & Claim** — Search and filter available food, claim with one click
- **Dashboard** — Manage your donations and track your claims
- **Status Tracking** — Available → Requested → Collected → Completed

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python + Flask |
| Frontend | HTML + CSS (no framework needed) |
| Database | SQLite |
| Auth | Flask Sessions + Werkzeug password hashing |
| Deploy | Render / Railway / Replit |

---

## 📁 Project Structure

```
shareplate/
├── app.py               # Flask backend (all routes)
├── requirements.txt     # Python dependencies
├── Procfile             # For Render/Railway deployment
├── shareplate.db        # SQLite database (auto-created)
├── templates/
│   ├── base.html        # Layout with navbar & footer
│   ├── index.html       # Homepage with hero + listings
│   ├── register.html    # Sign up page
│   ├── login.html       # Login page
│   ├── add_food.html    # Donate food form
│   ├── available.html   # Browse food listings
│   └── dashboard.html   # User dashboard
└── static/
    ├── css/style.css    # All styles
    └── js/main.js       # Small JS helpers
```

---

## 💻 Run Locally

```bash
# 1. Clone / download the project
cd shareplate

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# 5. Open in browser
# http://localhost:5000
```

---

## ☁️ Deploy on Render (Free)

1. Push project to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `gunicorn app:app`
6. Click **Deploy** ✅

---

## ☁️ Deploy on Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects Flask
4. Done! 🎉

---

## ☁️ Deploy on Replit

1. Upload files to Replit
2. In `.replit`, set `run = "python app.py"`
3. Click **Run** ✅

---

## 📸 Pages

| Page | URL |
|------|-----|
| Home | `/` |
| Register | `/register` |
| Login | `/login` |
| Browse Food | `/available` |
| Donate Food | `/add-food` |
| Dashboard | `/dashboard` |

---

## 🌱 Future Ideas

- Google Maps for pickup location
- SMS/Email notifications
- Image uploads for food posts
- NGO integration
- Mobile app (React Native)

---

**Made with ❤️ to end food waste · SharePlate 2024**
