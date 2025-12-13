import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ThemeState {
  mode: 'light' | 'dark';
  toggleMode: () => void;
  setMode: (mode: 'light' | 'dark') => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: 'dark',
      toggleMode: () =>
        set((state) => ({
          mode: state.mode === 'light' ? 'dark' : 'light',
        })),
      setMode: (mode) => set({ mode }),
    }),
    {
      name: 'theme-storage',
    }
  )
);