import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/admin/api';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth-storage');
    if (token) {
      try {
        const parsed = JSON.parse(token);
        if (parsed.state?.token) {
          config.headers.Authorization = `Bearer ${parsed.state.token}`;
        }
      } catch {
        // Invalid token format
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development';
    
    if (error.response?.status === 401) {
      // In dev mode, don't redirect if using mock token
      const authStorage = localStorage.getItem('auth-storage');
      if (isDev && authStorage) {
        try {
          const parsed = JSON.parse(authStorage);
          if (parsed.state?.token?.startsWith('dev-mock-token-')) {
            // Keep mock auth in dev mode
            return Promise.reject(error);
          }
        } catch {
          // Invalid storage format
        }
      }
      
      // Clear auth storage and redirect to login
      localStorage.removeItem('auth-storage');
      window.location.href = '/admin/login';
    }
    return Promise.reject(error);
  }
);

export default api;