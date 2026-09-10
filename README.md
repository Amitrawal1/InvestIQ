# 🚀 InvestIQ

Welcome to **InvestIQ**, an AI-powered financial intelligence platform.

This repository documents the development of a financial intelligence system that combines **financial data, market data, machine learning, Generative AI, and a modern web application** to help users research and understand companies and markets.

The goal is simple:

- 📊 Collect and organize financial and market data
- 🏢 Explore companies by sectors and industries
- 💰 Analyze financial fundamentals and stock data
- 🤖 Apply Machine Learning to financial data
- 🧠 Build AI-powered financial insights
- 📰 Analyze company and market news
- 🚀 Build a complete data-driven investment research platform

---

## 📂 Project

| Component | Description | Technologies |
|----------|-------------|--------------|
| 🗄️ **Financial Database** | Structured database containing company, sector, industry, market, and financial information. | MySQL |
| 📊 **Market Data Pipeline** | Collects and processes historical stock price data. | Node.js, Upstox API |
| 💰 **Financial Fundamentals** | Collects company financial information and key financial data. | Node.js, Upstox API |
| 🏢 **Company Classification** | Classifies companies into 10 sectors and 45 industries using automated classification and manual review. | JavaScript, Financial Data, Classification Rules |
| 🤖 **Machine Learning** | Analyzes financial and market data to generate company-level scores and insights. | Python, Pandas, NumPy, Scikit-Learn |
| 🧠 **AI Financial Intelligence** | Uses NLP, Generative AI, and LLMs for financial analysis and research. | NLP, Generative AI, LLMs |
| 💻 **Web Application** | Provides the user interface for company research, market analysis, and AI insights. | React.js, Tailwind CSS |

---

## 🗄️ Database

InvestIQ currently contains data for around **3,117 NSE-listed companies**.

Companies are organized using a **Sector → Industry → Company** structure.

```text
Sector
  ↓
Industry
  ↓
Company