const db = require("../config/db");
const {
    toNum,
    parseJson,
    RANKING_FIELDS,
    formatRankingRow
} = require("../services/rankingService");

const SMALLCAP_KEY = "NSE_INDEX|NIFTY SMLCAP 250";
const SMALLCAP_NAME = "NIFTY SMALLCAP 250";

// range -> months back (null = all history); 3y+ is downsampled to weekly closes
const PRICE_RANGES = { "6m": 6, "1y": 12, "3y": 36, "5y": 60, max: null };
const WEEKLY_RANGES = new Set(["3y", "5y", "max"]);

// Ratio fields exposed as latest_ratios (contract name -> key_metrics keys to try)
const RATIO_KEYS = {
    revenue_growth_yoy: ["revenue_growth_yoy", "revenue_yoy"],
    profit_growth_yoy: ["profit_growth_yoy", "net_profit_yoy"],
    revenue_ttm_growth: ["revenue_ttm_growth"],
    op_margin_ttm: ["op_margin_ttm"],
    net_margin_ttm: ["net_margin_ttm"],
    roe: ["roe"],
    roce: ["roce"],
    debt_to_equity: ["debt_to_equity"],
    current_ratio: ["current_ratio"],
    interest_coverage: ["interest_coverage", "interest_coverage_ttm"],
    cash_conversion: ["cash_conversion"],
};

const notFound = (res) => res.status(404).json({
    success: false,
    message: "Company not found"
});

// Case-insensitive symbol lookup (column collation is case-insensitive; upper-case anyway)
const findCompany = async (symbol) => {
    const [rows] = await db.query(`
        SELECT
            c.id,
            c.symbol,
            c.name,
            c.isin,
            c.series,
            c.market_segment,
            DATE_FORMAT(c.listing_date, '%Y-%m-%d') AS listing_date,
            s.name AS sector,
            s.slug AS sector_slug,
            i.name AS industry,
            c.website,
            c.description
        FROM companies c
        LEFT JOIN sectors s ON s.id = c.sector_id
        LEFT JOIN industries i ON i.id = c.industry_id
        WHERE c.symbol = ?
        LIMIT 1
    `, [String(symbol || "").trim().toUpperCase()]);

    return rows[0] || null;
};

const getCompanies = async (req, res) => {
    try {
        const {
            search,
            segment,
            sector,
            industry
        } = req.query;

        let query = `
            SELECT
                c.id,
                c.name,
                c.symbol,
                c.isin,
                c.exchange,
                c.market_segment,
                c.listing_date,
                c.series,
                s.name AS sector,
                i.name AS industry
            FROM companies c
            LEFT JOIN sectors s
                ON c.sector_id = s.id
            LEFT JOIN industries i
                ON c.industry_id = i.id
            WHERE 1 = 1
        `;

        const params = [];

        if (search) {
            query += `
                AND (
                    c.name LIKE ?
                    OR c.symbol LIKE ?
                )
            `;

            params.push(
                `%${search}%`,
                `%${search}%`
            );
        }

        if (segment) {
            query += ` AND c.market_segment = ?`;
            params.push(segment);
        }

        if (sector) {
            query += ` AND s.name = ?`;
            params.push(sector);
        }

        if (industry) {
            query += ` AND i.name = ?`;
            params.push(industry);
        }

        query += ` ORDER BY c.name ASC`;

        const [companies] = await db.query(query, params);

        res.status(200).json({
            success: true,
            count: companies.length,
            data: companies
        });

    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch companies"
        });
    }
};

// GET /companies/:symbol
const getCompanyBySymbol = async (req, res) => {
    try {
        const profile = await findCompany(req.params.symbol);

        if (!profile) {
            return notFound(res);
        }

        // All snapshots for this company (few rows); the latest global snapshot marks "current"
        const [rows] = await db.query(`
            SELECT
                ${RANKING_FIELDS},
                r.reasons,
                r.risks,
                r.model_version,
                DATE_FORMAT(r.snapshot_date, '%Y-%m-%d') AS snapshot_date,
                DATE_FORMAT((SELECT MAX(snapshot_date) FROM company_rankings), '%Y-%m-%d') AS latest_snapshot
            FROM company_rankings r
            JOIN companies c ON c.id = r.company_id
            LEFT JOIN sectors s ON s.id = c.sector_id
            LEFT JOIN industries i ON i.id = c.industry_id
            WHERE r.company_id = ?
            ORDER BY r.snapshot_date ASC
        `, [profile.id]);

        const current = rows.find((row) => row.snapshot_date === row.latest_snapshot);

        const ranking = current
            ? {
                ...formatRankingRow(current, true),
                reasons: parseJson(current.reasons, []) || [],
                risks: parseJson(current.risks, []) || [],
                model_version: current.model_version,
                snapshot_date: current.snapshot_date,
            }
            : null;

        res.json({
            profile,
            ranking,
            score_history: rows.map((row) => ({
                snapshot_date: row.snapshot_date,
                growth_score: toNum(row.growth_score),
                rank_overall: row.rank_overall,
            })),
        });
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch company"
        });
    }
};

// Keep one filing per period_end: consolidated over standalone, then the latest filing (revisions)
const pickPerPeriod = (rows) => {
    const best = new Map();

    for (const row of rows) {
        const current = best.get(row.period_end);
        const better = !current
            || (row.statement_type === "consolidated" && current.statement_type !== "consolidated")
            || (row.statement_type === current.statement_type
                && (row.filing_date || "") > (current.filing_date || ""));

        if (better) {
            best.set(row.period_end, row);
        }
    }

    return [...best.values()].sort((a, b) => a.period_end.localeCompare(b.period_end));
};

const ratio = (numerator, denominator) => (
    numerator === null || !denominator ? null : numerator / denominator
);

// GET /companies/:symbol/financials
const getCompanyFinancials = async (req, res) => {
    try {
        const company = await findCompany(req.params.symbol);

        if (!company) {
            return notFound(res);
        }

        const [[filings], [rankings]] = await Promise.all([
            db.query(`
                SELECT
                    DATE_FORMAT(period_end, '%Y-%m-%d') AS period_end,
                    DATE_FORMAT(filing_date, '%Y-%m-%d %H:%i:%s') AS filing_date,
                    statement_type,
                    months,
                    inc_revenue,
                    inc_net_profit,
                    inc_eps_basic,
                    inc_profit_before_tax,
                    inc_finance_costs,
                    bs_total_assets,
                    bs_total_equity,
                    bs_total_debt,
                    bs_current_assets,
                    bs_current_liabilities,
                    bs_cash_and_equivalents,
                    cf_operating_cf,
                    cf_capex,
                    cf_months
                FROM financial_filings
                WHERE company_id = ?
                    AND (parse_status IS NULL OR parse_status <> 'failed')
            `, [company.id]),
            db.query(`
                SELECT
                    r.key_metrics,
                    DATE_FORMAT(r.snapshot_date, '%Y-%m-%d') AS snapshot_date
                FROM company_rankings r
                WHERE r.company_id = ?
                    AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM company_rankings)
                LIMIT 1
            `, [company.id]),
        ]);

        const quarterly = pickPerPeriod(filings.filter((row) => row.months === 3
            && (row.inc_revenue !== null || row.inc_net_profit !== null)))
            .slice(-12)
            .map((row) => {
                const revenue = toNum(row.inc_revenue);
                const pbt = toNum(row.inc_profit_before_tax);
                const finance = toNum(row.inc_finance_costs);
                const netProfit = toNum(row.inc_net_profit);

                return {
                    period_end: row.period_end,
                    filing_date: row.filing_date,
                    statement_type: row.statement_type,
                    revenue,
                    net_profit: netProfit,
                    eps_basic: toNum(row.inc_eps_basic),
                    op_margin: pbt === null ? null : ratio(pbt + (finance || 0), revenue),
                    net_margin: ratio(netProfit, revenue),
                };
            });

        const BS_CF = [
            "bs_total_assets", "bs_total_equity", "bs_total_debt", "bs_current_assets",
            "bs_current_liabilities", "bs_cash_and_equivalents", "cf_operating_cf", "cf_capex",
        ];

        const halfYearly = pickPerPeriod(filings.filter((row) => BS_CF.some((key) => row[key] !== null)))
            .map((row) => {
                const operatingCf = toNum(row.cf_operating_cf);
                const capex = toNum(row.cf_capex);

                return {
                    period_end: row.period_end,
                    statement_type: row.statement_type,
                    total_assets: toNum(row.bs_total_assets),
                    total_equity: toNum(row.bs_total_equity),
                    total_debt: toNum(row.bs_total_debt),
                    current_assets: toNum(row.bs_current_assets),
                    current_liabilities: toNum(row.bs_current_liabilities),
                    cash_and_equivalents: toNum(row.bs_cash_and_equivalents),
                    operating_cf: operatingCf,
                    capex,
                    free_cash_flow: operatingCf === null || capex === null ? null : operatingCf - capex,
                    cf_months: row.cf_months,
                };
            });

        let latestRatios = null;

        if (rankings.length) {
            const metrics = parseJson(rankings[0].key_metrics, {}) || {};
            latestRatios = { as_of_period: metrics.as_of_period || null };

            for (const [name, keys] of Object.entries(RATIO_KEYS)) {
                const key = keys.find((candidate) => metrics[candidate] !== undefined);
                latestRatios[name] = key ? metrics[key] : null;
            }

            latestRatios.snapshot_date = rankings[0].snapshot_date;
        }

        res.json({
            quarterly,
            half_yearly: halfYearly,
            latest_ratios: latestRatios,
        });
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch financials"
        });
    }
};

// Keep the last trading day of each ISO week (volume summed over the week)
const weekKey = (dateStr) => {
    const date = new Date(`${dateStr}T00:00:00Z`);
    const monday = new Date(date);
    monday.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));

    return monday.toISOString().slice(0, 10);
};

const toWeekly = (rows) => {
    const weeks = new Map();

    for (const row of rows) {
        const key = weekKey(row.date);
        const prev = weeks.get(key);
        const volume = row.volume === null ? null : (prev && prev.volume !== null ? prev.volume : 0) + row.volume;

        weeks.set(key, { ...row, volume });
    }

    return [...weeks.values()];
};

// GET /companies/:symbol/prices?range=6m|1y|3y|5y|max
const getCompanyPrices = async (req, res) => {
    try {
        const range = Object.prototype.hasOwnProperty.call(PRICE_RANGES, req.query.range)
            ? req.query.range
            : "1y";
        const company = await findCompany(req.params.symbol);

        if (!company) {
            return notFound(res);
        }

        const months = PRICE_RANGES[range];
        const since = months === null ? "1900-01-01" : null;

        const dateFilter = since
            ? "price_date >= ?"
            : "price_date >= DATE_SUB(CURDATE(), INTERVAL ? MONTH)";
        const dateParam = since || months;

        const [[prices], [index]] = await Promise.all([
            db.query(`
                SELECT
                    DATE_FORMAT(price_date, '%Y-%m-%d') AS date,
                    close_price AS close,
                    volume
                FROM stock_prices
                WHERE company_id = ?
                    AND ${dateFilter}
                ORDER BY price_date ASC
            `, [company.id, dateParam]),
            db.query(`
                SELECT
                    DATE_FORMAT(price_date, '%Y-%m-%d') AS date,
                    close_price AS close
                FROM index_prices
                WHERE index_key = ?
                    AND ${dateFilter}
                ORDER BY price_date ASC
            `, [SMALLCAP_KEY, dateParam]),
        ]);

        let data = prices.map((row) => ({
            date: row.date,
            close: toNum(row.close),
            volume: row.volume === null ? null : Number(row.volume),
        }));

        if (WEEKLY_RANGES.has(range)) {
            data = toWeekly(data);
        }

        // Benchmark on the same dates as the company series
        const dates = new Set(data.map((row) => row.date));
        const benchmark = index
            .filter((row) => dates.has(row.date))
            .map((row) => ({ date: row.date, close: toNum(row.close) }));

        res.json({
            symbol: company.symbol,
            range,
            interval: WEEKLY_RANGES.has(range) ? "weekly" : "daily",
            data,
            benchmark: {
                name: SMALLCAP_NAME,
                data: benchmark,
            },
        });
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch prices"
        });
    }
};

module.exports = {
    getCompanies,
    getCompanyBySymbol,
    getCompanyFinancials,
    getCompanyPrices
};