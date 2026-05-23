# SalesIQ — AI-Powered Sales & Data Analytics Dashboard

> Full-stack Python dashboard with ML forecasting, interactive charts, authentication, and CSV/Excel upload. Built for job interviews and real-world use.

---

## Features

| Area | Capabilities |
|---|---|
| **Auth** | Register / Login / Logout, bcrypt password hashing, session management |
| **Data** | CSV & Excel upload, drag-drop zone, data preview table, multi-dataset support |
| **KPIs** | Revenue, Orders, Customers, Profit, Margin, Growth, Avg Order Value, Best Product |
| **Charts** | Sales trend, product revenue, category donut, region performance, profit+margin combo, heatmap, customer ranking |
| **ML Forecast** | Linear Regression + Seasonal decomposition, Random Forest (≥12mo), confidence bands, MAE/R² metrics |
| **Anomaly Detection** | Isolation Forest on monthly sales data |
| **Filters** | Date range, category, region — live KPI + chart refresh |
| **Export** | Filtered CSV download |
| **UI** | Dark theme, black/green palette, sidebar nav, responsive, Plotly interactive charts |

---

## Tech Stack

```
Backend   : Python 3.10+, Flask 3, Flask-Login, Flask-SQLAlchemy
Database  : SQLite (dev) / PostgreSQL (prod)
ML        : scikit-learn (LinearRegression, RandomForestRegressor, IsolationForest)
Data      : pandas, NumPy
Charts    : Plotly
Frontend  : HTML5, CSS3, Vanilla JS, Bootstrap 5, Bootstrap Icons
Fonts     : DM Sans, Space Mono (Google Fonts)
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourname/salesiq.git
cd salesiq/sales_dashboard

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python app.py
```

Visit `http://localhost:5000`

**Demo credentials:** `demo` / `demo123`

A sample dataset (119 rows) is pre-loaded for the demo account.

---

## Project Structure

```
sales_dashboard/
├── app.py                  # Flask app — routes, ML, API endpoints
├── requirements.txt
├── README.md
├── static/
│   ├── css/style.css       # Full dark theme stylesheet
│   └── sample_data.csv     # 119-row sample sales dataset
├── templates/
│   ├── base.html           # Sidebar layout, topbar, flash messages
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html      # KPI cards + 4 charts
│   ├── analytics.html      # Full 7-chart analytics grid + data table
│   ├── upload.html         # Drag-drop upload + dataset manager
│   └── forecast.html       # ML settings panel + forecast chart/table
├── uploads/                # User-uploaded files (gitignored)
├── database/               # SQLite file (gitignored)
└── reports/                # Future: PDF exports
```

---

## Expected CSV Columns

| Column | Type | Purpose |
|---|---|---|
| `Date` | Date | Trend analysis, forecasting |
| `Product` | Text | Product revenue ranking |
| `Category` | Text | Category segmentation |
| `Region` | Text | Geographic analysis |
| `Sales` | Float | Core revenue metric |
| `Profit` | Float | Margin analysis |
| `Quantity` | Int | Volume statistics |
| `Customer_Name` | Text | Customer ranking |

Column names are auto-detected (case-insensitive). You don't need all columns — the app adapts to what's present.

---

## ML Forecasting — How It Works

1. Aggregates raw data into monthly totals
2. Encodes seasonality as `sin(2π·month/12)` and `cos(2π·month/12)` features
3. Fits **Linear Regression** (default) or **Random Forest** on `[time_index, sin, cos]`
4. Predicts 3–12 months forward with ±15% confidence bands
5. Reports R² and MAE on training data
6. Saves result to `ForecastResult` table for history tracking

**Anomaly Detection** uses `IsolationForest` with 10% contamination rate on monthly aggregates to flag unusual sales periods.

---

## Database Schema

```
User
  id, username, email, password_hash, role, created_at

Dataset
  id, user_id, filename, original_filename, upload_date, row_count, columns_info, file_size

ForecastResult
  id, user_id, dataset_id, model_type, forecast_json, metrics_json, created_at
```

---

## Deployment

### Render / Railway

```bash
# Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

Set environment variables:
```
SECRET_KEY=your-secret-key-here
```

For PostgreSQL, change `SQLALCHEMY_DATABASE_URI` to use `DATABASE_URL` from env.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | hardcoded (change!) | Flask session key |
| `DATABASE_URL` | SQLite | Postgres URI for prod |
| `MAX_CONTENT_LENGTH` | 32MB | Max upload size |

---

## Interview Talking Points

- **Why Flask?** Lightweight, explicit, easy to extend. Django would add unnecessary overhead for a single-user analytics app. Flask-Login + Flask-SQLAlchemy provide auth + ORM without forcing conventions.
- **ML approach:** Seasonal Linear Regression is interpretable and stable on small datasets. The sin/cos encoding captures 12-month seasonality without requiring statsmodels or Prophet. Random Forest is available for non-linear patterns when data is sufficient (≥12 months).
- **Security:** Passwords hashed with `werkzeug.security.generate_password_hash` (PBKDF2-SHA256). Session-based auth with Flask-Login. Files namespaced by user ID to prevent enumeration.
- **Data preprocessing:** Column names normalized to Title_Case, date columns auto-detected and parsed, numeric columns found via keyword matching (handles "Revenue", "Sales", "Amount" etc.).
- **Architecture:** Single `app.py` keeps it portable. API routes (`/api/*`) return JSON consumed by Plotly in the frontend. Charts rendered client-side — no server-side PNG generation.

---

## Future Improvements

- [ ] PDF report generation (WeasyPrint / ReportLab)
- [ ] Email report scheduler (Celery + Redis)
- [ ] Real-time WebSocket KPI updates
- [ ] Multi-currency support
- [ ] Admin user management panel
- [ ] Docker + CI/CD pipeline
- [ ] Time series cross-validation for forecast accuracy
- [ ] Inventory management module
- [ ] REST API with JWT authentication

---

## Resume Description

> Developed a full-stack AI-powered Sales & Data Analytics Dashboard using Python, Flask, pandas, Plotly, and scikit-learn. Features include user authentication, CSV/Excel data upload, 7 interactive Plotly charts, real-time KPI cards with filter support, ML-based sales forecasting (Linear Regression + Random Forest with seasonal encoding), Isolation Forest anomaly detection, and SQLite persistence. Dark-themed responsive UI with sidebar navigation.
