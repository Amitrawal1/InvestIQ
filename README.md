# 🚀 InvestIQ

**AI-powered research and screening platform for the Indian stock market.**

InvestIQ studies **3,100+ NSE-listed companies** using three things: **share prices, company result filings, and daily news**. It turns them into one growth score per company, to help find small and mid-size companies that could grow over the next 6 months to 2 years.

🌐 **Live site:** [invest-iq-swart.vercel.app](https://invest-iq-swart.vercel.app)

![InvestIQ](docs/images/investiq-frame.png)

> ⚠️ InvestIQ is a **research tool, not investment advice**. You make the final decision.

---

## ✨ Features

| Page | What it does |
|------|--------------|
| 🏠 **Home** | Live IST clock, live market ticker, and all companies grouped into **10 sectors and 45 industries** |
| 📰 **News** | NSE company announcements collected **every 15 minutes**, each marked positive, negative or neutral by **FinBERT** |
| 🤖 **Predictor** | Every company gets a **growth score** and a label: **Strong, Positive, Neutral or Weak**. Includes a Top list (50), a Steady list and the full ranking, with search, sector/industry filters and sorting |
| 🏢 **Company** | Score with strengths and red flags, score history, price vs NIFTY Smallcap 250, quarterly results, balance sheet, cash flow, and latest news |
| 💼 **Portfolio** | Link an **Upstox** or **Zerodha** account (read-only). Shows value, P&L, an InvestIQ score for each holding, sector allocation and flagged holdings |
| 📅 **Events** | Type a news headline and see what the market did after similar events in the past |
| 🆕 **IPO Check** | Compares a new IPO's price with its peers, plus QIB subscription and market mood, and shows how similar IPOs did |
| 📈 **Track Record** | How every published ranking list has done against the index |
| ⚙️ **Settings** | Profile, password, linked brokers, light/dark theme, download data, delete account |

---

## 🧠 How the score works

The **InvestIQ model** (`investiq-v1`) combines three models:

| Model | Question it answers | Weight |
|-------|---------------------|--------|
| 📊 **Market model** | Is the price trend beating the NIFTY Smallcap 250? (52-week high, 50/200-day averages, 3 and 6 month returns, fewer down days) | Main part |
| 💰 **Financial model** | Is the business healthy and improving? (revenue and profit growth, profitability, debt, cash flow) | Second part |
| 📰 **News model** | Is the recent news good or bad? (FinBERT sentiment) | Small part |

```text
growth score = 0.95 x (0.70 market + 0.30 financial) + 0.05 news - penalties
```

| Score | Label |
|-------|-------|
| 75 and above | 🟢 Strong |
| 60 - 75 | 🔵 Positive |
| 40 - 60 | ⚪ Neutral |
| Below 40 | 🔴 Weak |

Companies without enough data are marked **Insufficient data** and are not ranked.
Banks, NBFCs and insurers use their own financial features.
Models are tested walk-forward on 2019 - 2026 data. Full results: [`docs/model-report.md`](docs/model-report.md).

---

## 🏗️ Architecture

```text
GitHub ──► Vercel: frontend (React)
       └─► Vercel: backend  (Node.js + Express API)
                       │
                       ▼
               TiDB Cloud (MySQL-compatible database)
                       ▲
GitHub Actions ── every 15 min ──► News pipeline (NSE announcements + FinBERT)
GitHub Actions ── weekday mornings ► Daily prices (Upstox)
GitHub Actions ── 1st and 16th ──► Rankings snapshot
```

The models are trained offline. Scores are saved in the database, and the website only reads them, so no ML server needs to run all the time.

---

## 🛠️ Tech Stack

| Layer | Tools |
|-------|-------|
| 💻 **Frontend** | React 18, Vite, Tailwind CSS, React Router, Motion, Chart.js, Axios |
| ⚙️ **Backend** | Node.js, Express, mysql2 |
| 🗄️ **Database** | TiDB Cloud (MySQL 8 compatible) |
| 🤖 **ML / Data** | Python, Pandas, NumPy, Scikit-Learn, XGBoost, FinBERT (Transformers + PyTorch) |
| 🔐 **Auth** | Google Sign-In, email/password (scrypt), JWT, AES-256-GCM encrypted broker tokens |
| 🔄 **Automation** | GitHub Actions |
| ☁️ **Hosting** | Vercel |
| 📡 **Data sources** | NSE (announcements, XBRL result filings), Upstox API (prices, live quotes, portfolios), Zerodha Kite Connect |

---

## 🗄️ Data

- **~3,117 NSE-listed companies**, organized as **Sector → Industry → Company**
- **Daily prices** from 2016 onwards (~4.3 million rows) plus NIFTY 50 and NIFTY Smallcap 250
- **Financial statements** from NSE XBRL filings: P&L, balance sheet and cash flow
- **News** from NSE announcements, last 30 days, with sentiment
- **Rankings** saved as dated snapshots, so score history can be shown

```text
Sector
  ↓
Industry
  ↓
Company
```

---

## 📂 Project Structure

```text
InvestIQ/
├── frontend/        React website (pages, components, API calls)
├── backend/         Express API (routes, controllers, services)
├── ml/
│   ├── news_pipeline/   NSE news + FinBERT sentiment
│   ├── financials/      NSE XBRL financial statements
│   ├── market_data/     Upstox daily prices
│   ├── growth_model/    Market model and labels
│   ├── financial_model/ Financial model
│   ├── rankings/        InvestIQ score and ranking snapshots
│   ├── events/          Market event study
│   └── ipo/             IPO check
├── docs/            Model report, rankings and auth docs
└── .github/workflows/   Scheduled jobs (news, prices, rankings, Upstox token)
```

---

## ▶️ Run Locally

```bash
# Backend (API on http://localhost:5500)
cd backend
npm install
npm run dev

# Frontend (site on http://localhost:5173)
cd frontend
npm install
npm run dev
```

The backend needs a `backend/.env` file with the database and API settings (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL`, Upstox and auth keys). Secrets are never committed.

---

## 📚 Docs

- [`docs/model-report.md`](docs/model-report.md): model results, failures and improvement plan
- [`docs/company-rankings.md`](docs/company-rankings.md): rankings table, API and pages
- [`docs/auth-and-portfolio.md`](docs/auth-and-portfolio.md): accounts, Google sign-in, broker linking and portfolio

---

## ⚠️ Disclaimer

InvestIQ is built for learning and research. It does **not** give buy or sell advice. Past results do not guarantee future returns. Always do your own research before investing.
