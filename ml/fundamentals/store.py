"""MySQL storage for NSE result filings (point-in-time: each row keeps its filing date)."""

import os

import mysql.connector
from dotenv import load_dotenv

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env")

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nse_financial_results (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    company_id INT NULL,
    symbol VARCHAR(50) NOT NULL,
    isin VARCHAR(20) NULL,
    company_name VARCHAR(255) NULL,

    period_type ENUM('quarterly', 'annual') NOT NULL,
    statement_type ENUM('standalone', 'consolidated') NOT NULL,
    period_start DATE NULL,
    period_end DATE NOT NULL,
    /* When the market could first see these numbers - used for point-in-time joins */
    filing_date DATETIME NOT NULL,
    audited VARCHAR(30) NULL,
    relating_to VARCHAR(50) NULL,

    revenue DECIMAL(20,2) NULL,
    other_income DECIMAL(20,2) NULL,
    total_income DECIMAL(20,2) NULL,
    total_expenses DECIMAL(20,2) NULL,
    raw_material_cost DECIMAL(20,2) NULL,
    employee_cost DECIMAL(20,2) NULL,
    finance_costs DECIMAL(20,2) NULL,
    depreciation DECIMAL(20,2) NULL,
    other_expenses DECIMAL(20,2) NULL,
    exceptional_items DECIMAL(20,2) NULL,
    profit_before_tax DECIMAL(20,2) NULL,
    tax DECIMAL(20,2) NULL,
    net_profit DECIMAL(20,2) NULL,
    reserves DECIMAL(20,2) NULL,
    paid_up_capital DECIMAL(20,2) NULL,
    equity DECIMAL(20,2) NULL,

    eps_basic DECIMAL(14,4) NULL,
    eps_diluted DECIMAL(14,4) NULL,
    face_value DECIMAL(10,2) NULL,
    debt_equity_ratio DECIMAL(12,4) NULL,
    debt_service_coverage DECIMAL(12,4) NULL,
    interest_service_coverage DECIMAL(12,4) NULL,

    nse_seq_number BIGINT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_filing (symbol, nse_seq_number),
    KEY idx_symbol_period (symbol, period_type, period_end),
    KEY idx_filing_date (filing_date)
)
"""

COLUMNS = [
    "company_id", "symbol", "isin", "company_name", "period_type", "statement_type",
    "period_start", "period_end", "filing_date", "audited", "relating_to",
    "revenue", "other_income", "total_income", "total_expenses", "raw_material_cost",
    "employee_cost", "finance_costs", "depreciation", "other_expenses",
    "exceptional_items", "profit_before_tax", "tax", "net_profit", "reserves",
    "paid_up_capital", "equity", "eps_basic", "eps_diluted", "face_value",
    "debt_equity_ratio", "debt_service_coverage", "interest_service_coverage",
    "nse_seq_number",
]

UPSERT_SQL = f"""
INSERT INTO nse_financial_results ({", ".join(COLUMNS)})
VALUES ({", ".join(["%s"] * len(COLUMNS))})
ON DUPLICATE KEY UPDATE
    {", ".join(f"{c} = VALUES({c})" for c in COLUMNS if c not in ("symbol", "nse_seq_number"))}
"""


def get_connection():
    load_dotenv(ENV_FILE, override=True)

    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=False,
    )


def ensure_schema(conn):
    cur = conn.cursor()
    cur.execute(TABLE_SQL)
    conn.commit()
    cur.close()


def company_id_by_symbol(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, symbol FROM companies WHERE symbol IS NOT NULL ORDER BY id")
    mapping = {}
    for company_id, symbol in cur.fetchall():
        mapping.setdefault(symbol.strip().upper(), company_id)
    cur.close()
    return mapping


def existing_seq_numbers(conn, symbol):
    cur = conn.cursor()
    cur.execute("SELECT nse_seq_number FROM nse_financial_results WHERE symbol = %s", (symbol,))
    values = {row[0] for row in cur.fetchall()}
    cur.close()
    return values


def save_rows(conn, rows):
    if not rows:
        return 0

    cur = conn.cursor()
    cur.executemany(UPSERT_SQL, [tuple(row.get(c) for c in COLUMNS) for row in rows])
    conn.commit()
    cur.close()

    return len(rows)
