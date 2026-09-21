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
