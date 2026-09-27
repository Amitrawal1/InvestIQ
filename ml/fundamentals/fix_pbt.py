"""One-off repair: `profit_before_tax` in nse_financial_results was stored as profit AFTER tax.

parse.py mapped PBT to NSE's `re_proloss_ord_act`, which is ordinary-activities profit after
tax. The correct PBT is that value + tax (verified against the XBRL ProfitBeforeTax of 211
filings: 210 match). This script:

  1. copies (id, profit_before_tax) into `nse_financial_results_pbt_backup` (once),
  2. sets profit_before_tax = profit_before_tax + tax on every row where both are present,
  3. prints before/after checks.

Run once from ml/:   python3 -m fundamentals.fix_pbt
Running it again does nothing (it refuses when the backup table already exists).
Undo:  UPDATE nse_financial_results r JOIN nse_financial_results_pbt_backup b USING (id)
       SET r.profit_before_tax = b.profit_before_tax;
"""

import sys

from news_pipeline.db import get_connection

BACKUP = "nse_financial_results_pbt_backup"


def pat_like_rows(cur):
    """Rows whose 'PBT' is within 1% of net profit, i.e. still look like profit after tax."""

    cur.execute("""
        SELECT COUNT(*) FROM nse_financial_results
        WHERE ABS(profit_before_tax - net_profit) <= GREATEST(0.05, ABS(net_profit) * 0.01)
    """)
    return cur.fetchone()[0]


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                (BACKUP,))
    if cur.fetchone()[0]:
        print(f"{BACKUP} already exists: the repair has already run. Nothing changed.")
        return 0

    print("Before: rows where 'PBT' looks like profit after tax:", pat_like_rows(cur))

    cur.execute(f"CREATE TABLE {BACKUP} AS SELECT id, profit_before_tax, NOW() AS backed_up_at FROM nse_financial_results")
    cur.execute(f"SELECT COUNT(*) FROM {BACKUP}")
    print("Backed up rows:", cur.fetchone()[0])

    cur.execute("""
        UPDATE nse_financial_results SET profit_before_tax = profit_before_tax + tax
        WHERE profit_before_tax IS NOT NULL AND tax IS NOT NULL
    """)
    print("Updated rows:", cur.rowcount)
    conn.commit()

    print("After: rows where 'PBT' looks like profit after tax:", pat_like_rows(cur))
    cur.execute("""
        SELECT SUM(total_income IS NOT NULL AND total_expenses IS NOT NULL AND
                   ABS(profit_before_tax - (total_income - total_expenses + COALESCE(exceptional_items, 0)))
                       <= GREATEST(0.05, ABS(profit_before_tax) * 0.01)),
               SUM(total_income IS NOT NULL AND total_expenses IS NOT NULL)
        FROM nse_financial_results
    """)
    print("After: PBT = total income - total expenses + exceptional in %s of %s checkable rows" % cur.fetchone())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
