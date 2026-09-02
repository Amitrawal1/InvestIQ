import os
import requests
from dotenv import load_dotenv

# Load backend .env
load_dotenv("/Users/amit/Desktop/InvestIQ/backend/.env", override=True)

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

if not API_KEY:
    print("ERROR: ALPHA_VANTAGE_API_KEY not found")
    exit()

BASE_URL = "https://www.alphavantage.co/query"


def fetch_data(function, symbol):
    params = {
        "function": function,
        "symbol": symbol,
        "apikey": API_KEY
    }

    response = requests.get(BASE_URL, params=params, timeout=30)

    print(f"\n========== {function} ==========")
    print("HTTP Status:", response.status_code)

    if response.status_code != 200:
        print("Request failed")
        return None

    data = response.json()

    # Alpha Vantage can return error/rate-limit messages
    if "Error Message" in data:
        print("API Error:", data["Error Message"])
        return None

    if "Note" in data:
        print("API Note:", data["Note"])
        return None

    print("Data received:", bool(data))

    return data


symbol = "RELIANCE.BSE"

overview = fetch_data("OVERVIEW", symbol)
income = fetch_data("INCOME_STATEMENT", symbol)
balance = fetch_data("BALANCE_SHEET", symbol)
cashflow = fetch_data("CASH_FLOW", symbol)


# -----------------------------
# OVERVIEW
# -----------------------------

if overview:
    print("\n========== COMPANY OVERVIEW ==========")

    fields = [
        "Name",
        "Symbol",
        "Exchange",
        "Currency",
        "Sector",
        "Industry",
        "MarketCapitalization",
        "PERatio",
        "PEGRatio",
        "BookValue",
        "DividendPerShare",
        "DividendYield",
        "EPS",
        "RevenueTTM",
        "ProfitMargin",
        "OperatingMarginTTM",
        "ReturnOnAssetsTTM",
        "ReturnOnEquityTTM",
        "RevenuePerShareTTM",
        "QuarterlyEarningsGrowthYOY",
        "QuarterlyRevenueGrowthYOY",
        "AnalystTargetPrice"
    ]

    for field in fields:
        print(f"{field}: {overview.get(field)}")


# -----------------------------
# INCOME STATEMENT
# -----------------------------

if income:
    print("\n========== INCOME STATEMENT ==========")

    annual_reports = income.get("annualReports", [])
    quarterly_reports = income.get("quarterlyReports", [])

    print("Annual reports:", len(annual_reports))
    print("Quarterly reports:", len(quarterly_reports))

    if annual_reports:
        latest = annual_reports[0]

        print("\nLatest Annual Report:")
        print("Fiscal Date:", latest.get("fiscalDateEnding"))
        print("Revenue:", latest.get("totalRevenue"))
        print("Operating Income:", latest.get("operatingIncome"))
        print("Net Income:", latest.get("netIncome"))
        print("EPS:", latest.get("reportedEPS"))


# -----------------------------
# BALANCE SHEET
# -----------------------------

if balance:
    print("\n========== BALANCE SHEET ==========")

    annual_reports = balance.get("annualReports", [])
    quarterly_reports = balance.get("quarterlyReports", [])

    print("Annual reports:", len(annual_reports))
    print("Quarterly reports:", len(quarterly_reports))

    if annual_reports:
        latest = annual_reports[0]

        print("\nLatest Annual Report:")
        print("Fiscal Date:", latest.get("fiscalDateEnding"))
        print("Total Assets:", latest.get("totalAssets"))
        print("Total Liabilities:", latest.get("totalLiabilities"))
        print("Total Equity:", latest.get("totalShareholderEquity"))
        print("Long Term Debt:", latest.get("longTermDebt"))
        print("Current Debt:", latest.get("currentDebt"))


# -----------------------------
# CASH FLOW
# -----------------------------

if cashflow:
    print("\n========== CASH FLOW ==========")

    annual_reports = cashflow.get("annualReports", [])
    quarterly_reports = cashflow.get("quarterlyReports", [])

    print("Annual reports:", len(annual_reports))
    print("Quarterly reports:", len(quarterly_reports))

    if annual_reports:
        latest = annual_reports[0]

        print("\nLatest Annual Report:")
        print("Fiscal Date:", latest.get("fiscalDateEnding"))
        print(
            "Operating Cash Flow:",
            latest.get("operatingCashflow")
        )
        print(
            "Capital Expenditure:",
            latest.get("capitalExpenditures")
        )
        print(
            "Free Cash Flow:",
            latest.get("freeCashFlow")
        )