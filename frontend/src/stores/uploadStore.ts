// src/stores/uploadStore.ts
import { create } from 'zustand'
import api from '../api/api'

export interface UploadJob {
  // поля из API
  id: string
  status: 'pending' | 'processing' | 'done' | 'failed'
  log: string
  raw_extracted: {
    fios:   string[]
    dobs:   string[]
    phones: string[]
    emails: string[]
  }
  uploaded_at:  string
  completed_at?: string
  record_id?:   number
  patient_id?:  number
  file_name:    string

  // наше локальное расширение
  file?: {
    name: string
    size: number
    type: string
  }
}

interface UploadState {
  currentUpload: File | null
  currentJob:    UploadJob | null
  isUploading:   boolean
  error:         string | null

  setCurrentUpload:   (file: File | null) => void
  uploadFile:         (file: File) => Promise<string>
  getJobById:         (id: string) => Promise<void>
  updateExtractedData:(
    jobId: string,
    data: Partial<UploadJob['raw_extracted']>
  ) => void
  clearUpload:        () => void
}

export const useUploadStore = create<UploadState>((set, get) => ({
  currentUpload: null,
  currentJob:    null,
  isUploading:   false,
  error:         null,

  setCurrentUpload: file =>
    set({ currentUpload: file }),

  uploadFile: async file => {
    set({ isUploading: true, error: null })
    const form = new FormData()
    form.append('archive_file', file)

    const { data } = await api.post<{ job_id: string }>(
      '/process-zip/',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )

    // создаём «скелет» записи
    const now = new Date().toISOString()
    const newJob: UploadJob = {
      id: data.job_id,
      status: 'pending',
      log: '',
      raw_extracted: { fios: [], dobs: [], phones: [], emails: [] },
      uploaded_at: now,
      file_name: file.name,
      file: { name: file.name, size: file.size, type: file.type },
    }

    set({ currentJob: newJob, isUploading: false })
    return data.job_id
  },

  getJobById: async id => {
    set({ error: null })
    try {
      // весь ответ сразу в UploadJob
      const { data: job } = await api.get<UploadJob>(`/task-status/${id}/`)
      // сохраняем серверные поля + не трогаем локальный file
      set({
        currentJob: {
          ...job,
          file: get().currentJob?.file
        }
      })
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to fetch job'
      set({ error: msg })
    }
  },

  updateExtractedData: (jobId, upd) =>
    set(state => {
      const j = state.currentJob
      if (!j || j.id !== jobId) return {}
      return {
        currentJob: {
          ...j,
          raw_extracted: { ...j.raw_extracted, ...upd }
        }
      }
    }),

  clearUpload: () =>
    set({
      currentUpload: null,
      currentJob:    null,
      isUploading:   false,
      error:         null,
    }),
}))
