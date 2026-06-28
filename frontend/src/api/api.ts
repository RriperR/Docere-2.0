import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/authStore';

type RetriableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

declare global {
  interface Window {
    api?: typeof api;
  }
}

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api';

const api = axios.create({ baseURL });
let refreshPromise: Promise<AuthTokenResponse> | null = null;

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().tokens?.access_token;
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetriableRequestConfig | undefined;
    const authState = useAuthStore.getState();
    const isAuthenticationRequest = ['/auth/login', '/auth/refresh', '/auth/register'].some((path) =>
      request?.url?.includes(path),
    );

    if (error.response?.status !== 401 || !request || request._retry || isAuthenticationRequest) {
      if (error.response?.status === 401 && (request?._retry || isAuthenticationRequest)) {
        authState.logout();
      }
      return Promise.reject(error);
    }

    const refreshToken = authState.tokens?.refresh_token;
    if (!refreshToken) {
      authState.logout();
      return Promise.reject(error);
    }

    request._retry = true;
    try {
      refreshPromise ??= axios
        .post<AuthTokenResponse>('/auth/refresh', { refresh_token: refreshToken }, { baseURL })
        .then((response) => response.data)
        .finally(() => {
          refreshPromise = null;
        });
      const tokens = await refreshPromise;
      useAuthStore.getState().setTokens(tokens);
      request.headers.Authorization = `Bearer ${tokens.access_token}`;
      return api(request);
    } catch (refreshError) {
      useAuthStore.getState().logout();
      return Promise.reject(refreshError);
    }
  }
);

if (import.meta.env.DEV) {
  window.api = api;
}

export default api;
