// src/stores/shareRequestsStore.ts
import { create } from 'zustand'
import api from '../api/api'

export interface SharedRecord {
  id: number
  record_id: number
  visit_date: string | null
  notes: string
  status: 'pending' | 'accepted' | 'declined'
  created: string
  updated: string
}

export interface ShareRequest {
  id: number
  from_user_fullname: string
  to_email: string
  to_user: number | null
  patient: number
  patient_name: string
  status: 'pending' | 'accepted' | 'declined'
  created_at: string
  responded_at: string | null
  shares: SharedRecord[]
}

interface ShareRequestsState {
  requests: ShareRequest[]
  isLoading: boolean
  error: string | null

  fetchAll: () => Promise<void>
  respond: (
    shareRequestId: number,
    recordShareId: number,
    action: 'accept' | 'decline'
  ) => Promise<void>
}

export const useShareRequestsStore = create<ShareRequestsState>((set) => ({
  requests: [],
  isLoading: false,
  error: null,

  fetchAll: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<ShareRequest[]>('/share-requests/')
      set({ requests: data, isLoading: false })
    } catch (e: any) {
      set({
        error: e.response?.data?.detail || e.message || 'Не удалось загрузить шаринги',
        isLoading: false
      })
    }
  },

  respond: async (shareRequestId, recordShareId, action) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/record-shares/${recordShareId}/respond/`, { action })
      // обновим локальный стор: изменим статус конкретного SharedRecord
      set(state => ({
        requests: state.requests.map(req => {
          if (req.id !== shareRequestId) return req
          return {
            ...req,
            shares: req.shares.map(s =>
              s.id === recordShareId ? { ...s, status: action === 'accept' ? 'accepted' : 'declined' } : s
            )
          }
        })
      }))
    } catch (e: any) {
      set({
        error: e.response?.data?.detail || e.message || 'Не удалось ответить на шаринг'
      })
    } finally {
      set({ isLoading: false })
    }
  },
}))
