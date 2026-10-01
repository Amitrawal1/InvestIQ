// Live track record of the published lists (investiq-v1 Top list and Steady list).
//
// For every snapshot that has a list, the list is "bought" at the first close strictly after the
// snapshot date (you act on the ranking the next session) in equal amounts and measured to the
// latest close, against the NIFTY SMALLCAP 250 over the same days. That gives:
//   snapshots[]  each published list held from its own date to today
//   chained[]    the list as actually followed: hold each list until the next snapshot's entry day,
//                then switch (equal weight, no costs), compounded from the first list
// Same conventions as the Python backtests (ml/rankings/time_machine.py): a company whose path has a
// one-day move above +100% or below -60% is a data break and is left out of that period; a company
// with no trade after the entry day keeps its entry price (counted as 0%).
// Read-only. Results are cached for 30 minutes per server instance.
const db = require("../config/db");
const { cached, toNum } = require("./rankingService");

const BENCHMARK = "NIFTY SMALLCAP 250";
const LISTS = { top: "top_list", steady: "steady_list" };
const BREAK_UP = 1.0;
const BREAK_DOWN = -0.6;
const TTL_MS = 30 * 60 * 1000;

const ymd = (d) => (d instanceof Date ? d.toISOString().slice(0, 10) : String(d).slice(0, 10));

// close series per company: Map(company_id -> [{ date, close }] sorted)
const loadPrices = async (ids, from) => {
    const out = new Map();
    for (let k = 0; k < ids.length; k += 500) {
        const chunk = ids.slice(k, k + 500);
        const [rows] = await db.query(
            `SELECT company_id, DATE_FORMAT(price_date, '%Y-%m-%d') AS date, close_price AS close
             FROM stock_prices WHERE company_id IN (?) AND price_date >= ? ORDER BY company_id, price_date`,
            [chunk, from]
        );
        for (const r of rows) {
            const close = toNum(r.close);
            if (!(close > 0)) continue;
            if (!out.has(r.company_id)) out.set(r.company_id, []);
            out.get(r.company_id).push({ date: r.date, close });
        }
    }
    return out;
};

// Return of one company from `entry` to `exit` (dates on the benchmark calendar); null if unusable
const companyReturn = (series, entry, exit) => {
    if (!series) return null;
    const window = series.filter((p) => p.date >= entry && p.date <= exit);
    if (!window.length || window[0].date !== entry) return null;           // no trade on the entry day
    for (let i = 1; i < window.length; i += 1) {
        const move = window[i].close / window[i - 1].close - 1;
        if (move > BREAK_UP || move < BREAK_DOWN) return null;              // data break
    }
    return window[window.length - 1].close / window[0].close - 1;
};

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

// Equal-weight result of `ids` from `entry` to `exit`
const listResult = (ids, prices, symbols, entry, exit) => {
    const rets = [];
    for (const id of ids) {
        const r = companyReturn(prices.get(id), entry, exit);
        if (r !== null) rets.push({ symbol: symbols.get(id), ret: r });
    }
    rets.sort((a, b) => b.ret - a.ret);
    return {
        measured: rets.length,
        return: mean(rets.map((x) => x.ret)),
        best: rets.slice(0, 3),
        worst: rets.slice(-3).reverse(),
        _rets: rets,
    };
};

const buildTrackRecord = async () => {
    const [members] = await db.query(`
        SELECT DATE_FORMAT(r.snapshot_date, '%Y-%m-%d') AS snapshot_date, r.company_id, r.symbol,
               JSON_EXTRACT(r.key_metrics, '$.top_list.in_list') = true AS top,
               JSON_EXTRACT(r.key_metrics, '$.steady_list.in_list') = true AS steady
        FROM company_rankings r
        WHERE r.model_version = 'investiq-v1'
          AND (JSON_EXTRACT(r.key_metrics, '$.top_list.in_list') = true
               OR JSON_EXTRACT(r.key_metrics, '$.steady_list.in_list') = true)
        ORDER BY r.snapshot_date
    `);
    if (!members.length) return { as_of: null, benchmark: BENCHMARK, lists: {} };

    const first = members[0].snapshot_date;
    const [idxRows] = await db.query(
        `SELECT DATE_FORMAT(price_date, '%Y-%m-%d') AS date, close_price AS close
         FROM index_prices WHERE index_name = ? AND price_date >= ? ORDER BY price_date`,
        [BENCHMARK, first]
    );
    const index = idxRows.map((r) => ({ date: r.date, close: toNum(r.close) })).filter((p) => p.close > 0);
    const asOf = index.length ? index[index.length - 1].date : null;
    const entryAfter = (snap) => index.find((p) => p.date > snap)?.date || null;
    const indexReturn = (entry, exit) => {
        const a = index.find((p) => p.date === entry);
        const b = index.find((p) => p.date === exit);
        return a && b ? b.close / a.close - 1 : null;
    };

    const ids = [...new Set(members.map((m) => m.company_id))];
    const symbols = new Map(members.map((m) => [m.company_id, m.symbol]));
    const prices = await loadPrices(ids, first);

    const lists = {};
    for (const [name, flag] of Object.entries({ top: "top", steady: "steady" })) {
        const bySnap = new Map();
        for (const m of members) {
            if (!Number(m[flag])) continue;
            if (!bySnap.has(m.snapshot_date)) bySnap.set(m.snapshot_date, []);
            bySnap.get(m.snapshot_date).push(m.company_id);
        }
        const snaps = [...bySnap.keys()].sort();
        if (!snaps.length) continue;

        // Each list held from its own entry day to the latest close
        const snapshots = snaps.map((snap) => {
            const entry = entryAfter(snap);
            const holdings = bySnap.get(snap);
            if (!entry || !asOf || entry >= asOf) {
                return { snapshot_date: snap, names: holdings.length, entry_date: entry, status: "waiting for prices" };
            }
            const res = listResult(holdings, prices, symbols, entry, asOf);
            const bench = indexReturn(entry, asOf);
            const beat = bench === null ? null : res._rets.filter((x) => x.ret > bench).length / (res._rets.length || 1);
            return {
                snapshot_date: snap, names: holdings.length, measured: res.measured, entry_date: entry, to: asOf,
                return: res.return, benchmark_return: bench, beat_index_share: beat, best: res.best, worst: res.worst,
            };
        });

        // The list as followed: switch to each new list on its entry day, compound
        const chained = [];
        let value = 1;
        let benchValue = 1;
        for (let i = 0; i < snaps.length; i += 1) {
            const entry = entryAfter(snaps[i]);
            const next = i + 1 < snaps.length ? entryAfter(snaps[i + 1]) : null;
            const exit = next && next <= asOf ? next : asOf;
            if (!entry || !exit || exit <= entry) break;
            const res = listResult(bySnap.get(snaps[i]), prices, symbols, entry, exit);
            const bench = indexReturn(entry, exit);
            if (res.return === null || bench === null) break;
            if (!chained.length) chained.push({ date: entry, value: 1, benchmark: 1 });
            value *= 1 + res.return;
            benchValue *= 1 + bench;
            chained.push({ date: exit, value, benchmark: benchValue });
        }

        lists[name] = {
            key: LISTS[name],
            first_snapshot: snaps[0],
            snapshots: snapshots.reverse(),
            chained,
            since_start: chained.length > 1
                ? { from: chained[0].date, to: chained[chained.length - 1].date,
                    return: chained[chained.length - 1].value - 1, benchmark_return: chained[chained.length - 1].benchmark - 1 }
                : null,
        };
    }

    return { as_of: asOf, benchmark: BENCHMARK, lists };
};

const getTrackRecord = () => cached("rankings:track-record", buildTrackRecord, (v) => v.as_of !== null, TTL_MS);

module.exports = { getTrackRecord, buildTrackRecord, companyReturn };
