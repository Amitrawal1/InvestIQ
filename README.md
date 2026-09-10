````markdown
# InvestIQ

InvestIQ is an AI-powered financial intelligence platform designed to help users understand companies, markets, sectors, industries, financial data, and investment-related information in one place.

The project combines financial data, machine learning, backend APIs, and a modern web interface to build a complete investment research platform.

---

## What We Are Building

InvestIQ aims to provide:

- Company search and company profiles
- Sector and industry-wise company discovery
- Stock prices and historical market data
- Financial fundamentals
- Company and market news
- AI/ML-based financial analysis
- Investment insights
- Company comparison

---

## System Overview

```text
                    INVESTIQ
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
      DATA             ML        APPLICATION
        │              │              │
        ↓              ↓              ↓
   Market Data    Classification    Frontend
   Fundamentals   ML Models         Backend API
   Company Data   AI Analysis       Database
   News           Predictions
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                Investment Insights
````

---

## Technology Stack

### Frontend

* React.js
* Tailwind CSS
* JavaScript

### Backend

* Node.js
* Express.js
* REST APIs

### Database

* MySQL

### Machine Learning

* Python
* Pandas
* NumPy
* Scikit-learn
* NLP
* Generative AI / LLMs

### Financial Data

* NSE data
* Upstox API
* Company fundamentals
* Historical stock prices
* Financial and market news

---

## Database Structure

The database is mainly organized around companies, sectors, and industries.

```text
                    sectors
                       │
                       │ 1 : N
                       ↓
                  industries
                       │
                       │ 1 : N
                       ↓
                   companies
```

### Sectors

InvestIQ uses 10 major sectors:

1. Financial Services
2. Technology
3. Healthcare & Pharmaceuticals
4. Energy & Utilities
5. Automobile & Mobility
6. Consumer & FMCG
7. Industrials & Infrastructure
8. Metals, Mining & Chemicals
9. Real Estate & Construction
10. Services & Others

### Industries

Companies are classified into 45 industries, including:

* IT Services
* Software
* Artificial Intelligence
* Semiconductor
* Hardware
* Solar Energy
* Renewable Energy
* Power
* Oil & Gas
* Banking
* Insurance
* NBFC
* Asset Management
* Pharmaceuticals
* Hospitals
* Diagnostics
* Medical Devices
* Automobiles
* Auto Components
* Electric Vehicles
* Mobility Services
* FMCG
* Food & Beverages
* Retail
* Consumer Durables
* Consumer Services
* Capital Goods
* Engineering
* Construction
* Infrastructure
* Manufacturing
* Metals & Mining
* Cement
* Chemicals
* Specialty Chemicals
* Real Estate
* Real Estate Development
* Building Materials
* Telecom
* Logistics
* Aviation
* Hotels & Hospitality
* Media & Entertainment
* Education
* Other Services

---

## Company Classification

A major part of InvestIQ is automatically classifying companies into the correct industry.

```text
Company Data
     ↓
Data Cleaning
     ↓
Company Profile / Business Information
     ↓
Classification Rules + ML
     ↓
45 Industries
     ↓
10 Sectors
     ↓
MySQL Database
```

The classification system uses company information, business descriptions, financial data, and external company data to determine the most suitable industry.

Confidence levels are also used so that uncertain classifications can be reviewed manually.

---

## Current Database

The current company universe contains **3,117 NSE companies**.

Current classification status:

```text
Total Companies       : 3,117
Classified Companies  : 2,801
Unclassified          : 316
Industry/Sector Error : 0
```

The remaining companies are being processed using additional fallback classification methods.

---

## Data Pipeline

InvestIQ follows a structured data pipeline:

```text
                    RAW DATA
                       ↓
              Data Cleaning
                       ↓
             Data Validation
                       ↓
           Feature Engineering
                       ↓
              ML / AI Models
                       ↓
              Model Results
                       ↓
              Backend / API
                       ↓
                  Frontend
```

The pipeline is designed to be improved continuously as more data becomes available.

---

## Machine Learning

The ML layer is being developed to analyze financial and market data.

The planned workflow includes:

```text
Historical Market Data
          +
Financial Fundamentals
          +
Company Information
          ↓
   Feature Engineering
          ↓
      ML Models
     ┌────┼────┐
     ↓    ↓    ↓
   Model Model Model
     └────┼────┘
          ↓
   Predictions / Scores
          ↓
   Investment Insights
```

The ML system will be improved iteratively as data quality and feature engineering become better.

---

## Backend Architecture

The backend provides APIs for the frontend and handles financial data.

```text
Frontend
   ↓
Express REST API
   ↓
Controllers
   ↓
Services
   ↓
MySQL Database
   ↓
Financial Data Providers
```

Main backend areas include:

* Company APIs
* Sector APIs
* Stock Price APIs
* News APIs
* Market Data Services
* Company Classification

---

## Project Structure

```text
InvestIQ/
│
├── frontend/
│
├── backend/
│   ├── config/
│   ├── controllers/
│   ├── routes/
│   ├── services/
│   ├── scripts/
│   └── data/
│
├── ml/
│   ├── data/
│   ├── models/
│   └── scripts/
│
└── README.md
```

---

## Development Roadmap

### Phase 1 — Data Infrastructure

* Collect company data
* Clean and validate data
* Build company database
* Add historical stock prices
* Add financial fundamentals

### Phase 2 — Company Classification

* Create sector and industry taxonomy
* Classify companies
* Add confidence scoring
* Handle uncertain companies using fallback methods

### Phase 3 — Machine Learning

* Feature engineering
* Build ML models
* Train and evaluate models
* Generate company-level scores

### Phase 4 — AI Financial Intelligence

* Financial text analysis
* Company insights
* News analysis
* AI-assisted investment research

### Phase 5 — Product

* Company dashboard
* Sector and industry exploration
* Stock analysis
* AI insights
* Investment research interface

---

## Goal

The goal of InvestIQ is to build a complete financial intelligence platform where users can move from:

```text
Company
   ↓
Financial Data
   ↓
Market Data
   ↓
Industry & Sector
   ↓
ML Analysis
   ↓
AI Insights
   ↓
Investment Decision Support
```

InvestIQ is being built as a data-driven system where the data pipeline, machine learning models, backend, database, and frontend work together.

---

## Project Status

🚧 **InvestIQ is currently under active development.**

The data infrastructure, company database, financial data pipeline, and company classification system are currently being developed. The machine learning and AI layers will be expanded as the underlying data becomes more complete and reliable.

```
```
