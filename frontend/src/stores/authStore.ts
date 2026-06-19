import { create } from 'zustand';
import api from '../api/api';

export type UserRole = 'doctor' | 'patient' | 'admin';

interface TokenData {
  access_token: string;
  token_type: string;
}

interface BackendAuthUser {
  id: string;
  fio: string;
  email: string;
  phone: string;
  date_of_birth: string | null;
  role: UserRole;
  status: string;
}

interface UserData {
  id: string;
  fio: string;
  email: string;
  phone: string;
  date_of_birth: string | null;
  role: UserRole;
  status: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  birthday: string | null;
  photo: string | null;
  username: string;
}

interface AuthState {
  tokens: TokenData | null;
  user: UserData | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  setTokens: (tokens: TokenData) => void;
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

type ValidationDetailItem = {
  loc?: unknown;
  msg?: unknown;
};

const toFio = (firstName: string, lastName: string, middleName: string | null): string => {
  return [lastName, firstName, middleName ?? '']
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .join(' ');
};

const splitFio = (fio: string): { first_name: string; last_name: string; middle_name: string | null } => {
  const parts = fio
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0);

  const [lastName = '', firstName = '', ...rest] = parts;
  return {
    first_name: firstName,
    last_name: lastName,
    middle_name: rest.length > 0 ? rest.join(' ') : null,
  };
};

const toUserData = (payload: BackendAuthUser): UserData => {
  const fioParts = splitFio(payload.fio);
  return {
    id: payload.id,
    fio: payload.fio,
    email: payload.email,
    phone: payload.phone,
    date_of_birth: payload.date_of_birth,
    role: payload.role,
    status: payload.status,
    first_name: fioParts.first_name,
    last_name: fioParts.last_name,
    middle_name: fioParts.middle_name,
    birthday: payload.date_of_birth,
    photo: null,
    username: payload.email,
  };
};

const parseStoredJson = <T,>(key: string): T | null => {
  const value = localStorage.getItem(key);
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
};

const formatValidationDetailItem = (item: ValidationDetailItem): string | null => {
  const msg = typeof item.msg === 'string' ? item.msg : null;
  if (!msg) {
    return null;
  }

  if (Array.isArray(item.loc) && item.loc.length > 0) {
    const path = item.loc
      .map((segment) => String(segment))
      .join('.');
    return `${path}: ${msg}`;
  }

  return msg;
};

const normalizeApiErrorMessage = (error: unknown, fallback: string): string => {
  const maybeError = error as {
    response?: { data?: { detail?: unknown } };
    message?: unknown;
  };

  const detail = maybeError?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim().length > 0) {
    if (detail === 'Internal server error') {
      return fallback;
    }
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }
        if (item && typeof item === 'object') {
          return formatValidationDetailItem(item as ValidationDetailItem);
        }
        return null;
      })
      .filter((message): message is string => Boolean(message));

    if (messages.length > 0) {
      return messages.join('; ');
    }
  }

  if (typeof maybeError?.message === 'string' && maybeError.message.trim().length > 0) {
    return maybeError.message;
  }

  return fallback;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  tokens: parseStoredJson<TokenData>('authTokens'),
  user: parseStoredJson<UserData>('authUserData'),
  isLoading: false,
  error: null,
  isAuthenticated: !!parseStoredJson<TokenData>('authTokens')?.access_token,

  setTokens: (tokens) => {
    localStorage.setItem('authTokens', JSON.stringify(tokens));
    set({ tokens, isAuthenticated: true });
  },

  register: async (firstName, lastName, middleName, email, phone, birthday, password) => {
    set({ isLoading: true, error: null });
    try {
      await api.post('/auth/register', {
        fio: toFio(firstName, lastName, middleName),
        email,
        phone: phone ?? '',
        password,
        date_of_birth: birthday,
      });
      await get().login(email, password);
    } catch (err: any) {
      set({
        error: normalizeApiErrorMessage(err, 'Не удалось зарегистрироваться. Попробуйте позже.'),
        isLoading: false,
      });
      throw err;
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const { data: tokenData } = await api.post<TokenData>('/auth/login', {
        email,
        password,
      });

      get().setTokens(tokenData);

      const { data: backendUser } = await api.get<BackendAuthUser>('/auth/me');
      const user = toUserData(backendUser);
      localStorage.setItem('authUserData', JSON.stringify(user));
      set({ user, isLoading: false, isAuthenticated: true });
    } catch (err: any) {
      set({
        error: normalizeApiErrorMessage(err, 'Не удалось войти. Проверьте email и пароль или попробуйте позже.'),
        isLoading: false,
      });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('authTokens');
    localStorage.removeItem('authUserData');
    set({ tokens: null, user: null, isAuthenticated: false, error: null, isLoading: false });
  },

  restoreSession: () => {
    const tokens = parseStoredJson<TokenData>('authTokens');
    const user = parseStoredJson<UserData>('authUserData');
    set({
      tokens,
      user,
      isAuthenticated: !!tokens?.access_token,
    });
  },

  updateProfile: async () => {
    const message = 'Profile update endpoint is not implemented on backend yet';
    set({ error: message, isLoading: false });
    throw new Error(message);
  },
}));
