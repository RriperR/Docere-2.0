import { create } from 'zustand'
import api from '../api/api'

interface NotificationsState {
  unread: number; revision: number; version: string
  refresh: () => Promise<void>; reset: () => void
}
export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  unread: 0, revision: 0, version: '',
  refresh: async () => {
    const data = (await api.get<{ unread: number; version: string }>('/notifications/count')).data
    set({ unread: data.unread, version: data.version, revision: get().revision + (data.version !== get().version ? 1 : 0) })
  },
  reset: () => set({ unread: 0, version: '', revision: 0 }),
}))
