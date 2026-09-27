import axios from 'axios';

const api = axios.create({
  baseURL: '', // Using the Vite server proxy
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercept requests to inject Auth Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;

// --- InvestIQ backend endpoints (proxied by Vite: /api/* -> backend) ---

// Short timeout so the UI falls back quickly when the backend isn't running
export const getSectors = () =>
  api.get('/api/sectors', { timeout: 5000 }).then((res) => res.data);

export const getCompaniesBySector = (sectorName) =>
  api.get('/api/companies', { params: { sector: sectorName }, timeout: 8000 }).then((res) => res.data.data);

// News + FinBERT sentiment. `params` accepts:
// limit, offset, symbol, sector, importance, sentiment, confident, search, from, to
export const getNews = (params = {}) =>
  api.get('/api/news', { params, timeout: 10000 }).then((res) => res.data);

export const getNewsStats = () =>
  api.get('/api/news/stats', { timeout: 8000 }).then((res) => res.data.data);

// Live NIFTY / SENSEX / blue-chip quotes from Upstox: [{ name, price, change, changePct }]
export const getMarketTicker = () =>
  api.get('/api/market/ticker', { timeout: 10000 }).then((res) => res.data.data);

// --- Company rankings (docs/company-rankings.md) ---

// params: sector (slug), industry, search, label, sort (rank|score|name|return_1y), page, limit
// -> { snapshot_date, model_version, total, page, limit, data: [RankingRow] }
export const getRankings = (params = {}) =>
  api.get('/api/rankings', { params, timeout: 10000 }).then((res) => res.data);

// -> { snapshot_date, model_version, next_update, ranked, unranked, method, snapshots }
export const getRankingsMeta = () =>
  api.get('/api/rankings/meta', { timeout: 8000 }).then((res) => res.data);

// -> [{ industry, company_count, ranked_count, avg_score, top_symbol }]
export const getSectorIndustries = (slug) =>
  api.get(`/api/sectors/${encodeURIComponent(slug)}/industries`, { timeout: 8000 }).then((res) => res.data);

// -> { profile, ranking, score_history }
export const getCompanyDetails = (symbol) =>
  api.get(`/api/companies/${encodeURIComponent(symbol)}`, { timeout: 10000 }).then((res) => res.data);

// -> { quarterly, half_yearly, latest_ratios }
export const getCompanyFinancials = (symbol) =>
  api.get(`/api/companies/${encodeURIComponent(symbol)}/financials`, { timeout: 10000 }).then((res) => res.data);

// range: 6m | 1y | 3y | 5y | max -> { symbol, data: [{date, close, volume}], benchmark: { name, data } }
export const getCompanyPrices = (symbol, range = '1y') =>
  api.get(`/api/companies/${encodeURIComponent(symbol)}/prices`, { params: { range }, timeout: 15000 }).then((res) => res.data);

// Company announcements with FinBERT sentiment
export const getCompanyNews = (companyId, limit = 30) =>
  api.get(`/api/news/company/${companyId}`, { params: { limit }, timeout: 10000 }).then((res) => res.data);
