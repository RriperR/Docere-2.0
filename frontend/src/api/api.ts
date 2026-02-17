// src/api/api.ts
import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { useAuthStore }           from '../stores/authStore';


const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const api = axios.create({
  baseURL,
})

// перед каждым запросом подставляем актуальный access
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().tokens?.access;
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ловим 401 и рефрешим токен один раз на запрос
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError & { config?: AxiosRequestConfig & { _retry?: boolean } }) => {
    const originalRequest = error.config!;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;
      console.log('[api] 401 detected, attempting token refresh…');

      try {
        const newAccess = await useAuthStore.getState().refreshAccessToken();
        console.log('[api] got new access token, retrying original request');

        // подставляем новый токен вручную
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newAccess}`;

        // повторяем тот же запрос
        return api(originalRequest);
      } catch (refreshErr) {
        console.log('[api] refresh failed, logging out');
        useAuthStore.getState().logout();
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  }
);

// после всех interceptor’ов
if (import.meta.env.DEV) {
  // @ts-ignore
  window.api = api;
}

export default api;
