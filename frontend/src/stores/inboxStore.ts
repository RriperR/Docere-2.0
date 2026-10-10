import { create } from 'zustand'
import api from '../api/api'
interface Counts { tasks: number; unread_events: number }
interface InboxState { counts: Counts | null; error: boolean; revision: number; refresh: () => Promise<void>; reset: () => void }
let generation = 0
export const useInboxStore = create<InboxState>((set, get) => ({
  counts: null, error: false, revision: 0,
  reset: () => { generation++; set({ counts: null, error: false, revision: 0 }) },
  refresh: async () => {
    const request = ++generation
    try {
      const data = (await api.get<Counts>('/inbox/counts')).data
      if (request === generation) set({ counts: data, error: false, revision: get().revision + 1 })
    } catch { if (request === generation) set({ error: true }) }
  },
}))
