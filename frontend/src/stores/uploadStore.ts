import { create } from 'zustand'

import api from '../api/api'

export interface ImportFileDraft {
  path: string
  filename: string
  mime_type: string
  size_bytes: number
  is_dicom: boolean
}

export interface ImportDuplicateRecord {
  record_id: string
  patient_passport_id: string
  title: string | null
  record_type: string
  event_date: string
  status: string
  match_reason: string
}

export interface ImportRecordGroupDraft {
  group_id: string
  record_type: string
  event_date: string | null
  event_date_candidates: string[]
  title: string
  payload_json: Record<string, unknown>
  files: ImportFileDraft[]
  duplicate_candidates: ImportDuplicateRecord[]
}

export interface ImportPatientMatch {
  id: string
  fio: string
  date_of_birth: string | null
  status: string
  match_score: number
  match_type: 'exact' | 'fuzzy'
}

export interface ImportPatientDraft {
  candidate_id: string
  fio: string | null
  date_of_birth: string | null
  sources: string[]
  existing_matches: ImportPatientMatch[]
  record_groups: ImportRecordGroupDraft[]
}

export interface ImportReport extends Record<string, unknown> {
  message?: string
  source_archive?: string
  patients?: ImportPatientDraft[]
  files_total?: number
  warnings?: string[]
  skipped_files?: number
  patients_created?: number
  records_created?: number
  attachments_created?: number
}

export interface UploadJob {
  id: string
  status: 'queued' | 'running' | 'needs_review' | 'completed' | 'failed' | 'completed_with_warnings'
  original_filename: string | null
  archive_storage_key: string | null
  size_bytes: number | null
  report_json: ImportReport
  review_decisions: ImportPatientDecision[]
  review_updated_at: string | null
  created_at: string
  finished_at: string | null
  file?: {
    name: string
    size: number
    type: string
  }
}

export interface ImportRecordGroupDecision {
  group_id: string
  action: 'create' | 'skip'
  record_type?: string
  event_date?: string | null
  title?: string
  allow_possible_duplicate?: boolean
}

export interface ImportPatientDecision {
  candidate_id: string
  action: 'existing' | 'create' | 'skip'
  patient_passport_id?: string
  fio?: string
  date_of_birth?: string | null
  record_groups: ImportRecordGroupDecision[]
}

interface UploadState {
  currentUpload: File | null
  currentJob: UploadJob | null
  jobs: UploadJob[]
  isUploading: boolean
  isLoadingJobs: boolean
  isResolving: boolean
  isSavingReviewDraft: boolean
  reviewDraftError: string | null
  progress: number
  error: string | null

  setCurrentUpload: (file: File | null) => void
  uploadFile: (file: File) => Promise<string>
  listJobs: () => Promise<void>
  getJobById: (id: string) => Promise<void>
  resolveJob: (id: string, patients: ImportPatientDecision[]) => Promise<void>
  saveReviewDraft: (id: string, patients: ImportPatientDecision[]) => Promise<string | null>
  clearUpload: () => void
}

type ApiError = {
  response?: { data?: { detail?: unknown } }
  message?: string
}

const normalizeError = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) return fallback
  const apiError = error as ApiError
  const detail = apiError.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const payload = detail as { code?: unknown }
    if (payload.code === 'duplicate_confirmation_required') {
      return 'Появилась похожая запись. Проверьте дубликаты и подтвердите импорт повторно.'
    }
    if (payload.code === 'event_date_required') {
      return 'Укажите дату события для каждой импортируемой медицинской записи.'
    }
  }
  return apiError.message || fallback
}

export const useUploadStore = create<UploadState>((set, get) => ({
  currentUpload: null,
  currentJob: null,
  jobs: [],
  isUploading: false,
  isLoadingJobs: false,
  isResolving: false,
  isSavingReviewDraft: false,
  reviewDraftError: null,
  progress: 0,
  error: null,

  setCurrentUpload: (file) => set({ currentUpload: file }),

  uploadFile: async (file) => {
    set({ isUploading: true, progress: 0, error: null })
    const form = new FormData()
    form.append('file', file)

    try {
      const { data } = await api.post<UploadJob>('/archives/imports', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          if (!event.total) return
          set({ progress: Math.round((event.loaded / event.total) * 100) })
        },
      })
      const job = {
        ...data,
        file: { name: file.name, size: file.size, type: file.type },
      }
      set({ currentJob: job, jobs: [job, ...get().jobs.filter((item) => item.id !== job.id)], isUploading: false, progress: 100 })
      return data.id
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось загрузить архив'), isUploading: false, progress: 0 })
      throw error
    }
  },

  listJobs: async () => {
    set({ isLoadingJobs: true, error: null })
    try {
      const { data } = await api.get<UploadJob[]>('/archives/imports')
      set({ jobs: data, isLoadingJobs: false })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось загрузить список импортов'), isLoadingJobs: false })
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
        jobs: get().jobs.map((item) => (item.id === data.id ? data : item)),
      })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось получить статус импорта') })
    }
  },

  resolveJob: async (id, patients) => {
    set({ isResolving: true, error: null })
    try {
      const { data } = await api.post<UploadJob>(`/archives/imports/${id}/resolve`, { decisions: patients })
      set({
        currentJob: data,
        jobs: get().jobs.map((item) => (item.id === data.id ? data : item)),
        isResolving: false,
      })
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось подтвердить импорт'), isResolving: false })
      throw error
    }
  },

  saveReviewDraft: async (id, patients) => {
    set({ isSavingReviewDraft: true, reviewDraftError: null })
    try {
      const { data } = await api.put<{
        decisions: ImportPatientDecision[]
        updated_at: string | null
      }>(`/archives/imports/${id}/review-draft`, { decisions: patients })
      set((state) => ({
        currentJob: state.currentJob?.id === id
          ? {
              ...state.currentJob,
              review_decisions: data.decisions,
              review_updated_at: data.updated_at,
            }
          : state.currentJob,
        isSavingReviewDraft: false,
      }))
      return data.updated_at
    } catch (error: unknown) {
      const message = normalizeError(error, 'Не удалось сохранить черновик проверки')
      set({ reviewDraftError: message, isSavingReviewDraft: false })
      throw error
    }
  },

  clearUpload: () =>
    set({
      currentUpload: null,
      currentJob: null,
      jobs: [],
      isUploading: false,
      isLoadingJobs: false,
      isResolving: false,
      isSavingReviewDraft: false,
      reviewDraftError: null,
      progress: 0,
      error: null,
    }),
}))
