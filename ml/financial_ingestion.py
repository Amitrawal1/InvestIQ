import os
import requests
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

ACCESS_TOKEN_FILE = BASE_DIR / "ml" / "upstox_access_token.txt"

BASE_URL = "https://api.upstox.com/v2/fundamentals"


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# =========================================================
# ACCESS TOKEN
# =========================================================

def get_access_token():

    with open(ACCESS_TOKEN_FILE, "r") as f:
        return f.read().strip()


# =========================================================
# API
# =========================================================

def fetch_fundamental(endpoint, isin, params=None):

    access_token = get_access_token()

    url = f"{BASE_URL}/{isin}/{endpoint}"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    print(f"{endpoint}: HTTP {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        return None

    data = response.json()

    if data.get("status") != "success":
        print("API returned unsuccessful status")
        return None

    return data.get("data")


# =========================================================
# HELPERS
# =========================================================

def get_history_value(history, name, period):

    if not history:
        return None

    for item in history:

        if (
            item.get("name") == name
            and item.get("period") == period
        ):
            return item.get("value")

    return None

def get_category_history(income_statement, category, period):

    for item in income_statement:

        if item.get("category") == category:

            for history_item in item.get("history", []):

                if history_item.get("period") == period:
                    return history_item.get("value")

    return None


def period_to_date(period):

    month, year = period.split()

    month_number = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12
    }

    month_num = month_number[month]

    if month_num == 12:
        next_month = 1
        next_year = int(year) + 1
    else:
        next_month = month_num + 1
        next_year = int(year)

    from datetime import date

    first_day_next_month = date(
        next_year,
        next_month,
        1
    )

    from datetime import timedelta

    last_day = first_day_next_month - timedelta(days=1)

    return last_day


# =========================================================
# MAIN INGESTION
# =========================================================

def ingest_company(company_id, isin):

    print("\n========================================")
    print("Starting financial ingestion")
    print("Company ID :", company_id)
    print("ISIN       :", isin)
    print("========================================")

    # -----------------------------------------------------
    # FETCH DATA
    # -----------------------------------------------------

    print("\nFetching financial data...")

    income_data = fetch_fundamental(
        "income-statement",
        isin,
        {
            "type": "consolidated",
            "time_period": "quarterly",
            "fs": "true"
        }
    )

    balance_data = fetch_fundamental(
        "balance-sheet",
        isin,
        {
            "type": "consolidated",
            "fs": "true"
        }
    )

    cashflow_data = fetch_fundamental(
        "cash-flow",
        isin,
        {
            "type": "consolidated",
            "fs": "true"
        }
    )

    if not income_data:
        print("Income statement data unavailable.")
        return

    if not balance_data:
        print("Balance sheet data unavailable.")
        return

    if not cashflow_data:
        print("Cash flow data unavailable.")
        return

    print("\nAPI data fetched successfully.")

    # -----------------------------------------------------
    # EXTRACT DATA
    # -----------------------------------------------------

    income_statement = income_data.get(
        "income_statement",
        []
    )
    


    income_full = income_data.get(
        "full_statement",
        []
    )

    balance_full = balance_data.get(
        "full_statement",
        []
    )

    cashflow_full = cashflow_data.get(
        "full_statement",
        []
    )

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    print("Connected to MySQL.")

    # =====================================================
    # YEARLY DATA
    # =====================================================

    yearly_periods = set()

    for item in income_full:
        if item.get("period"):
            yearly_periods.add(item.get("period"))

    for item in balance_full:
        if item.get("period"):
            yearly_periods.add(item.get("period"))

    for item in cashflow_full:
        if item.get("period"):
            yearly_periods.add(item.get("period"))

    processed_yearly = 0

    for period in sorted(yearly_periods):

        period_end_date = period_to_date(period)

        revenue = get_history_value(
            income_full,
            "Revenue",
            period
        )

        other_income = get_history_value(
            income_full,
            "Other Income",
            period
        )

        total_revenue = get_history_value(
            income_full,
            "Total Revenue",
            period
        )

        total_expenses = get_history_value(
            income_full,
            "Total Expenses",
            period
        )

        profit_before_tax = get_history_value(
            income_full,
            "Profit Before Tax",
            period
        )

        tax = get_history_value(
            income_full,
            "Tax",
            period
        )

        profit_after_tax = get_history_value(
            income_full,
            "PAT",
            period
        )

        eps = get_history_value(
            income_full,
            "EPS Basic",
            period
        )

        total_assets = get_history_value(
            balance_full,
            "Total Assets",
            period
        )

        total_equity = get_history_value(
            balance_full,
            "Equity Capital",
            period
        )

        operating_cash_flow = get_history_value(
            cashflow_full,
            "Cash flow from Operations",
            period
        )

        investing_cash_flow = get_history_value(
            cashflow_full,
            "Cash flow from Investing",
            period
        )

        financing_cash_flow = get_history_value(
            cashflow_full,
            "Cash flow from Financing",
            period
        )

        query = """
            INSERT INTO financial_statements (
                company_id,
                isin,
                statement_type,
                period_type,
                period_end_date,

                revenue,
                operating_profit,
                net_profit,
                eps,

                total_assets,
                total_debt,
                total_equity,

                operating_cash_flow,
                investing_cash_flow,
                financing_cash_flow,

                other_income,
                total_revenue,
                total_expenses,
                profit_before_tax,
                tax,
                profit_after_tax
            )

            VALUES (
                %s, %s, 'consolidated', 'yearly', %s,

                %s, NULL, %s, %s,

                %s, NULL, %s,

                %s, %s, %s,

                %s, %s, %s, %s, %s, %s
            )

            ON DUPLICATE KEY UPDATE

                revenue = VALUES(revenue),
                net_profit = VALUES(net_profit),
                eps = VALUES(eps),

                total_assets = VALUES(total_assets),
                total_equity = VALUES(total_equity),

                operating_cash_flow =
                    VALUES(operating_cash_flow),

                investing_cash_flow =
                    VALUES(investing_cash_flow),

                financing_cash_flow =
                    VALUES(financing_cash_flow),

                other_income =
                    VALUES(other_income),

                total_revenue =
                    VALUES(total_revenue),

                total_expenses =
                    VALUES(total_expenses),

                profit_before_tax =
                    VALUES(profit_before_tax),

                tax =
                    VALUES(tax),

                profit_after_tax =
                    VALUES(profit_after_tax)
        """

        values = (
            company_id,
            isin,
            period_end_date,

            revenue,
            profit_after_tax,
            eps,

            total_assets,
            total_equity,

            operating_cash_flow,
            investing_cash_flow,
            financing_cash_flow,

            other_income,
            total_revenue,
            total_expenses,
            profit_before_tax,
            tax,
            profit_after_tax
        )

        cursor.execute(query, values)

        processed_yearly += 1

    # =====================================================
    # QUARTERLY DATA
    # =====================================================

    quarterly_periods = set()

    for item in income_statement:

        for history_item in item.get("history", []):

            if history_item.get("period"):
                quarterly_periods.add(
                    history_item.get("period")
                )


    processed_quarterly = 0


    for period in sorted(quarterly_periods):

        period_end_date = period_to_date(period)

        revenue = get_category_history(
            income_statement,
            "revenue",
            period
        )

        operating_profit = get_category_history(
            income_statement,
            "operating_profit",
            period
        )

        net_profit = get_category_history(
            income_statement,
            "net_profit",
            period
        )

        query = """
            INSERT INTO financial_statements (
                company_id,
                isin,
                statement_type,
                period_type,
                period_end_date,

                revenue,
                operating_profit,
                net_profit
            )

            VALUES (
                %s, %s, 'consolidated', 'quarterly', %s,

                %s, %s, %s
            )

            ON DUPLICATE KEY UPDATE

                revenue = VALUES(revenue),

                operating_profit =
                    VALUES(operating_profit),

                net_profit =
                    VALUES(net_profit)
        """

        values = (
            company_id,
            isin,
            period_end_date,

            revenue,
            operating_profit,
            net_profit
        )

        cursor.execute(query, values)

        processed_quarterly += 1
    

    # =====================================================
    # COMMIT
    # =====================================================

    conn.commit()

    cursor.close()
    conn.close()

    print("\n========================================")
    print("Financial ingestion completed.")
    print("Yearly records processed    :", processed_yearly)
    print("Quarterly records processed :", processed_quarterly)
    print("========================================")


# =========================================================
# TEST COMPANY
# =========================================================

if __name__ == "__main__":

    # Reliance Industries
    ingest_company(
        company_id=1844,
        isin="INE002A01018"
    )