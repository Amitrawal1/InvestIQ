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

// --- Accounts (docs/auth-and-portfolio.md) ---

// Requests whose 401 means "wrong password", not "session expired"
const PASSWORD_CHECKS = ['/api/auth/login', '/api/auth/register', '/api/auth/password', '/api/auth/google'];

// A 401 on an authenticated request means the token is missing/invalid/expired:
// tell AuthContext so it can sign the user out cleanly.
api.interceptors.response.use(
  (res) => res,
  (error) => {
    const { config, response } = error;
    const url = config?.url || '';
    const passwordCheck =
      PASSWORD_CHECKS.includes(url) || (url === '/api/auth/me' && config?.method === 'delete');
    if (response?.status === 401 && localStorage.getItem('token') && !passwordCheck) {
      window.dispatchEvent(new Event('investiq:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// Best human-readable message from an API error
export const apiError = (err, fallback = 'Something went wrong. Try again.') => {
  if (err?.response?.data?.message) return err.response.data.message;
  if (err?.response?.data?.error && typeof err.response.data.error === 'string') return err.response.data.error;
  if (err?.code === 'ECONNABORTED' || !err?.response) return "Can't reach InvestIQ right now. Check your connection and try again.";
  if (err.response.status >= 500) return 'InvestIQ had a problem on its side. Try again in a moment.';
  return fallback;
};

// -> { token, user }
export const loginUser = (email, password) =>
  api.post('/api/auth/login', { email, password }, { timeout: 15000 }).then((res) => res.data);

// -> { token, user }
export const registerUser = (username, email, password) =>
  api.post('/api/auth/register', { username, email, password }, { timeout: 15000 }).then((res) => res.data);

// -> { google_client_id } (null when Google sign-in isn't set up on the server)
export const getAuthConfig = () => api.get('/api/auth/config', { timeout: 8000 }).then((res) => res.data);

// Google Identity Services ID token -> { token, user } (creates the account on first use)
export const googleSignIn = (credential) =>
  api.post('/api/auth/google', { credential }, { timeout: 15000 }).then((res) => res.data);

// -> { user }
export const getMe = () => api.get('/api/auth/me', { timeout: 10000 }).then((res) => res.data.user);

// { username?, email? } -> { user }
export const updateMe = (changes) => api.patch('/api/auth/me', changes, { timeout: 10000 }).then((res) => res.data.user);

// -> { success: true }
export const changePassword = (current_password, new_password) =>
  api.post('/api/auth/password', { current_password, new_password }, { timeout: 15000 }).then((res) => res.data);

// Deletes the account, its broker links and synced data
// Accounts without a password (Google-only) confirm with their email instead
export const deleteAccount = (password, confirmEmail) =>
  api
    .delete('/api/auth/me', { data: confirmEmail ? { confirm_email: confirmEmail } : { password }, timeout: 20000 })
    .then((res) => res.data);

// --- Broker linking + portfolio (read-only) ---

// -> [{ broker, connected, broker_user_name, broker_user_id, token_valid, token_expires_at,
//       connected_at, last_synced_at, last_error, configured }]
export const getBrokers = () => api.get('/api/brokers', { timeout: 10000 }).then((res) => res.data);

// -> { url } of the broker's own login page
export const connectBroker = (broker) =>
  api.post(`/api/brokers/${encodeURIComponent(broker)}/connect`, {}, { timeout: 10000 }).then((res) => res.data);

// -> { synced_at, totals }; 409 { code: "TOKEN_EXPIRED" } when the broker session has lapsed
export const syncBroker = (broker) =>
  api.post(`/api/brokers/${encodeURIComponent(broker)}/sync`, {}, { timeout: 60000 }).then((res) => res.data);

export const disconnectBroker = (broker, deleteData = false) =>
  api
    .delete(`/api/brokers/${encodeURIComponent(broker)}`, { params: deleteData ? { delete_data: 1 } : {}, timeout: 20000 })
    .then((res) => res.data);

// -> { connections, summary, holdings, positions, funds, insights, history }
export const getPortfolio = () => api.get('/api/portfolio', { timeout: 20000 }).then((res) => res.data);

// -> { as_of, benchmark, lists: { top|steady: { first_snapshot, since_start, chained: [{date, value, benchmark}], snapshots: [...] } } }
export const getTrackRecord = () =>
  api.get('/api/rankings/track-record', { timeout: 20000 }).then((res) => res.data);

// --- Market events study (history, not a forecast; backend/data/events.json) ---
export const getEvents = (params = {}) => api.get('/api/events', { params, timeout: 10000 }).then((res) => res.data);
export const getEventTypes = () => api.get('/api/events/types', { timeout: 10000 }).then((res) => res.data);
export const getEvent = (id) => api.get(`/api/events/${encodeURIComponent(id)}`, { timeout: 10000 }).then((res) => res.data);
// params: type, stance, horizon (21d|63d|126d), level (sector|theme)
export const getEventPlaybook = (params) => api.get('/api/events/playbook', { params, timeout: 10000 }).then((res) => res.data);
export const classifyEvent = (text, horizon = '63d') =>
  api.post('/api/events/classify', { text, horizon }, { timeout: 10000 }).then((res) => res.data);
