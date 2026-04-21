import { create } from 'zustand'

import api from '../api/api'

export type ShareStatus = 'pending' | 'accepted' | 'declined' | 'cancelled' | 'revoked'

export interface ShareUser {
  id: string
  fio: string
  email: string
  role: string
}

export interface SharedRecord {
  id: string
  record_id: string
  patient_passport_id: string | null
  status: ShareStatus
  created_at: string
  responded_at: string | null
  revoked_at: string | null
}

export interface ShareRequest {
  id: string
  from_user: ShareUser
  to_user: ShareUser
  status: ShareStatus
  message: string | null
  shares: SharedRecord[]
  created_at: string
  responded_at: string | null
  cancelled_at: string | null
  revoked_at: string | null
}

export interface CreateShareResult {
  request: ShareRequest | null
  skipped_record_ids: string[]
}

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
  message?: string
}

interface ShareRequestsState {
  inbox: ShareRequest[]
  outbox: ShareRequest[]
  isLoading: boolean
  error: string | null

  createShareRequest: (payload: {
    to_user_email: string
    record_ids: string[]
    message?: string
  }) => Promise<CreateShareResult>
  fetchInbox: () => Promise<void>
  fetchOutbox: () => Promise<void>
  acceptRequest: (requestId: string) => Promise<void>
  declineRequest: (requestId: string) => Promise<void>
  cancelRequest: (requestId: string) => Promise<void>
  revokeRequest: (requestId: string) => Promise<void>
}

const normalizeError = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) {
    return fallback
  }

  const apiError = error as ApiError
  return apiError.response?.data?.detail || apiError.message || fallback
}

export const useShareRequestsStore = create<ShareRequestsState>((set, get) => ({
  inbox: [],
  outbox: [],
  isLoading: false,
  error: null,

  createShareRequest: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<CreateShareResult>('/share-requests', payload)
      await get().fetchOutbox()
      set({ isLoading: false })
      return data
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось создать запрос на sharing'),
        isLoading: false,
      })
      throw error
    }
  },

  fetchInbox: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<ShareRequest[]>('/share-requests/inbox')
      set({ inbox: data, isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось загрузить входящие sharing-запросы'),
        isLoading: false,
      })
    }
  },

  fetchOutbox: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<ShareRequest[]>('/share-requests/outbox')
      set({ outbox: data, isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось загрузить исходящие sharing-запросы'),
        isLoading: false,
      })
    }
  },

  acceptRequest: async (requestId) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/share-requests/${requestId}/accept`)
      await get().fetchInbox()
      set({ isLoading: false })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось принять sharing-запрос'), isLoading: false })
      throw error
    }
  },

  declineRequest: async (requestId) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/share-requests/${requestId}/decline`)
      await get().fetchInbox()
      set({ isLoading: false })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось отклонить sharing-запрос'), isLoading: false })
      throw error
    }
  },

  cancelRequest: async (requestId) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/share-requests/${requestId}/cancel`)
      await get().fetchOutbox()
      set({ isLoading: false })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось отменить sharing-запрос'), isLoading: false })
      throw error
    }
  },

  revokeRequest: async (requestId) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/share-requests/${requestId}/revoke`)
      await get().fetchOutbox()
      set({ isLoading: false })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось отозвать доступ'), isLoading: false })
      throw error
    }
  },
}))
