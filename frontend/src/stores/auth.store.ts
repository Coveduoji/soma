import { create } from 'zustand';
import type { AuthUser } from '../types/models';
import { authApi } from '../api/auth';

const TOKEN_KEY = 'soma_jwt';

export const getToken = () => localStorage.getItem(TOKEN_KEY) || '';
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

interface AuthState {
  user: AuthUser | null;
  authReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (u: AuthUser | null) => void;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  authReady: false,
  login: async (username, password) => {
    const { token, user } = await authApi.login(username, password);
    setToken(token);
    set({ user });
  },
  logout: () => {
    clearToken();
    set({ user: null });
  },
  setUser: (u) => set({ user: u }),
  init: async () => {
    if (getToken()) {
      try {
        const user = await authApi.me();
        set({ user, authReady: true });
      } catch {
        clearToken();
        set({ user: null, authReady: true });
      }
    } else {
      set({ authReady: true });
    }
  },
}));
