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
