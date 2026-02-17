// src/stores/authStore.ts
import { create } from 'zustand';
import api from '../api/api';
import axios from 'axios';

interface TokenData {
  access: string;
  refresh: string;
}

interface UserData {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  email: string;
  phone: string | null;
  birthday: string | null;
  photo: string | null;
  role: 'doctor' | 'patient' | 'admin';
}

interface AuthState {
  tokens: TokenData | null;
  user: UserData | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;

  /** Сохранить пару токенов */
  setTokens: (tokens: TokenData) => void;
  /** Обновить access из refresh */
  refreshAccessToken: () => Promise<string>;

  register: (
    firstName: string,
    lastName: string,
    middleName: string | null,
    email: string,
    phone: string | null,
    birthday: string | null,
    password: string
  ) => Promise<void>;

  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  restoreSession: () => void;

  updateProfile: (updates: {
    first_name?: string;
    last_name?: string;
    middle_name?: string | null;
    phone?: string | null;
    birthday?: string | null;
    photo?: string | null;
  }) => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  tokens: JSON.parse(localStorage.getItem('authTokens') || 'null'),
  user: JSON.parse(localStorage.getItem('authUserData') || 'null'),
  isLoading: false,
  error: null,
  isAuthenticated: !!localStorage.getItem('authTokens'),

  setTokens: (tokens) => {
    localStorage.setItem('authTokens', JSON.stringify(tokens));
    set({ tokens, isAuthenticated: true });
  },

  refreshAccessToken: async () => {
    const tokens = get().tokens;
    if (!tokens?.refresh) {
      throw new Error('No refresh token available');
    }
    // POST /token/refresh/ возвращает { access: string }
    const { data } = await axios.post<{ access: string }>(
      `${import.meta.env.VITE_API_BASE_URL}/token/refresh/`,
      { refresh: tokens.refresh }
    );

    // Собираем новый объект, сохранив старый refresh
    const newTokens: TokenData = {
      access: data.access,
      refresh: tokens.refresh,
    };

    // Сохраняем и в Zustand, и в localStorage
    set({ tokens: newTokens });
    localStorage.setItem('authTokens', JSON.stringify(newTokens));

    return data.access;
  },

  register: async (
    firstName,
    lastName,
    middleName,
    email,
    phone,
    birthday,
    password
  ) => {
    set({ isLoading: true, error: null });
    try {
      // 1) Регистрация
      await api.post('/user/register/', {
        first_name:  firstName,
        last_name:   lastName,
        middle_name: middleName,
        email,
        phone,
        birthday,
        password,
      });

      // 2) Получаем токены
      const { data: tokens } = await api.post<TokenData>('/token/', {
        username: email,
        password,
      });

      // 3) Сохраняем токены
      get().setTokens(tokens);

      // 4) Запрашиваем профиль (интерцептор axios подставит access)
      const { data: user } = await api.get<UserData>('/user/me/');
      localStorage.setItem('authUserData', JSON.stringify(user));
      set({ user, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Registration failed',
        isLoading: false,
      });
      throw err;
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      // 1) Получаем токены
      const { data: tokens } = await api.post<TokenData>('/token/', {
        username: email,
        password,
      });

      // 2) Сохраняем токены
      get().setTokens(tokens);

      // 3) Запрашиваем профиль
      const { data: user } = await api.get<UserData>('/user/me/');
      localStorage.setItem('authUserData', JSON.stringify(user));
      set({ user, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Login failed',
        isLoading: false,
      });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('authTokens');
    localStorage.removeItem('authUserData');
    set({ tokens: null, user: null, isAuthenticated: false });
  },

  restoreSession: () => {
    const tokens = JSON.parse(localStorage.getItem('authTokens') || 'null');
    const user   = JSON.parse(localStorage.getItem('authUserData') || 'null');
    set({ tokens, user, isAuthenticated: !!tokens });
  },

  updateProfile: async (updates) => {
    set({ isLoading: true, error: null });
    try {
      const { data: updated } = await api.put<UserData>('/user/me/', updates);
      localStorage.setItem('authUserData', JSON.stringify(updated));
      set({ user: updated, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data ? JSON.stringify(err.response.data) : 'Update failed',
        isLoading: false,
      });
      throw err;
    }
  },
}));
