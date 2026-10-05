import { create } from 'zustand'
import api from '../api/api'

interface NotificationsState {
  unread: number; revision: number; version: string
  refresh: () => Promise<void>; reset: () => void
}
let requestGeneration = 0

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  unread: 0, revision: 0, version: '',
  refresh: async () => {
    const request = ++requestGeneration
    const data = (await api.get<{ unread: number; version: string }>('/notifications/count')).data
    if (request !== requestGeneration) return
    set({ unread: data.unread, version: data.version, revision: get().revision + (data.version !== get().version ? 1 : 0) })
  },
  reset: () => { requestGeneration += 1; set({ unread: 0, version: '', revision: 0 }) },
}))
