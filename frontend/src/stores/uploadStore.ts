import { create } from 'zustand'

import api from '../api/api'

export interface UploadJob {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'completed_with_warnings'
  original_filename: string | null
  archive_storage_key: string | null
  size_bytes: number | null
  report_json: Record<string, unknown>
  created_at: string
  finished_at: string | null
  file?: {
    name: string
    size: number
    type: string
  }
}

interface UploadState {
  currentUpload: File | null
  currentJob: UploadJob | null
  isUploading: boolean
  error: string | null

  setCurrentUpload: (file: File | null) => void
  uploadFile: (file: File) => Promise<string>
  getJobById: (id: string) => Promise<void>
  clearUpload: () => void
}

type ApiError = {
  response?: { data?: { detail?: string } }
  message?: string
}

const normalizeError = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) return fallback
  const apiError = error as ApiError
  return apiError.response?.data?.detail || apiError.message || fallback
}

export const useUploadStore = create<UploadState>((set, get) => ({
  currentUpload: null,
  currentJob: null,
  isUploading: false,
  error: null,

  setCurrentUpload: (file) => set({ currentUpload: file }),

  uploadFile: async (file) => {
    set({ isUploading: true, error: null })
    const form = new FormData()
    form.append('file', file)

    try {
      const { data } = await api.post<UploadJob>('/archives/imports', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const job = {
        ...data,
        file: { name: file.name, size: file.size, type: file.type },
      }
      set({ currentJob: job, isUploading: false })
      return data.id
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось загрузить архив'), isUploading: false })
      throw error
    }
  },

  getJobById: async (id) => {
    set({ error: null })
    try {
      const { data } = await api.get<UploadJob>(`/archives/imports/${id}`)
      set({
        currentJob: {
          ...data,
          file: get().currentJob?.file,
        },
      })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось получить статус импорта') })
    }
  },

  clearUpload: () =>
    set({
      currentUpload: null,
      currentJob: null,
      isUploading: false,
      error: null,
    }),
}))
