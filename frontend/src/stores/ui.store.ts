import { create } from 'zustand';
import type { TermMode } from '../lib/terms';

// 持久化 key 与旧实现保持一致，避免用户设置丢失。
const TERM_KEY = 'term_mode';
const THEME_KEY = 'theme';

interface UiState {
  termMode: TermMode;
  darkMode: boolean;
  setTermMode: (m: TermMode) => void;
  toggleDark: () => void;
  setDarkMode: (d: boolean) => void;
}

const initialTerm = (): TermMode => (localStorage.getItem(TERM_KEY) === 'bio' ? 'bio' : 'sec');
const initialDark = (): boolean => localStorage.getItem(THEME_KEY) === 'dark';

export const useUiStore = create<UiState>((set) => ({
  termMode: initialTerm(),
  darkMode: initialDark(),
  setTermMode: (m) => {
    localStorage.setItem(TERM_KEY, m);
    set({ termMode: m });
  },
  toggleDark: () =>
    set((s) => {
      const next = !s.darkMode;
      localStorage.setItem(THEME_KEY, next ? 'dark' : 'light');
      return { darkMode: next };
    }),
  setDarkMode: (d) => {
    localStorage.setItem(THEME_KEY, d ? 'dark' : 'light');
    set({ darkMode: d });
  },
}));
