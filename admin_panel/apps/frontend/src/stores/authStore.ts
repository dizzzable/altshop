import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../api/client';

interface User {
  id: string;
  username: string;
  role: string;
  telegramId?: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post('/auth/login', { username, password });
          const { access_token, user } = response.data;
          
          set({
            token: access_token,
            user,
            isAuthenticated: true,
            isLoading: false,
          });
          
          // Set token in API client
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.message || 'Login failed',
          });
          throw error;
        }
      },

      logout: () => {
        set({
          token: null,
          user: null,
          isAuthenticated: false,
        });
        delete api.defaults.headers.common['Authorization'];
      },

      checkAuth: async () => {
        const { token } = get();
        if (!token) {
          set({ isAuthenticated: false });
          return;
        }

        try {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          const response = await api.post('/auth/verify');
          if (response.data.valid) {
            set({ isAuthenticated: true });
          } else {
            get().logout();
          }
        } catch {
          get().logout();
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);