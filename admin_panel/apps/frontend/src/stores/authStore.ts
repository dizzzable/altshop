import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../api/client';

const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development';

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
  devLogin: () => void;
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
        
        // Dev mode: mock authentication
        if (isDev) {
          // Simulate API delay
          await new Promise(resolve => setTimeout(resolve, 500));
          
          const mockUser: User = {
            id: 'dev-user-1',
            username: username || 'dev',
            role: 'super_admin',
            telegramId: '123456789',
          };
          
          const mockToken = 'dev-mock-token-' + Date.now();
          
          set({
            token: mockToken,
            user: mockUser,
            isAuthenticated: true,
            isLoading: false,
          });
          
          api.defaults.headers.common['Authorization'] = `Bearer ${mockToken}`;
          return;
        }
        
        // Production: real API call
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

      devLogin: () => {
        if (!isDev) return;
        
        const mockUser: User = {
          id: 'dev-user-1',
          username: 'dev',
          role: 'super_admin',
          telegramId: '123456789',
        };
        
        const mockToken = 'dev-mock-token-' + Date.now();
        
        set({
          token: mockToken,
          user: mockUser,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        
        api.defaults.headers.common['Authorization'] = `Bearer ${mockToken}`;
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

        // Dev mode: always valid if token exists
        if (isDev && token.startsWith('dev-mock-token-')) {
          set({ isAuthenticated: true });
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
          // In dev mode, don't logout on verify error
          if (!isDev) {
            get().logout();
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);