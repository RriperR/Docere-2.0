import { create } from 'zustand'

import api from '../api/api'

export type DoctorRoleApplicationStatus = 'pending' | 'approved' | 'rejected'
export type DoctorRoleReviewStatus = 'pending' | 'approved' | 'rejected'

export interface DoctorRoleReviewerCandidate {
  id: string
  fio: string
  email: string
  role: 'doctor' | 'admin'
  specialty: string | null
}

export interface DoctorRoleReview {
  id: string
  reviewer_user_id: string
  reviewer_fio: string
  reviewer_email: string
  reviewer_role: 'doctor' | 'admin'
  reviewer_specialty: string | null
  status: DoctorRoleReviewStatus
  note: string | null
  created_at: string
  responded_at: string | null
}

export interface DoctorRoleApplication {
  id: string
  applicant_user_id: string
  applicant_fio: string
  applicant_email: string
  applicant_date_of_birth: string | null
  specialty: string
  status: DoctorRoleApplicationStatus
  reviews: DoctorRoleReview[]
  created_at: string
  resolved_at: string | null
}

interface DoctorRoleApplicationsState {
  specialties: string[]
  reviewers: DoctorRoleReviewerCandidate[]
  mine: DoctorRoleApplication[]
  inbox: DoctorRoleApplication[]
  isLoading: boolean
  isSubmitting: boolean
  error: string | null
  fetchSpecialties: () => Promise<void>
  fetchReviewers: (specialty: string) => Promise<void>
  fetchMine: () => Promise<void>
  fetchInbox: () => Promise<void>
  createApplication: (specialty: string, reviewerUserIds: string[]) => Promise<DoctorRoleApplication>
  reviewApplication: (
    applicationId: string,
    decision: 'approved' | 'rejected',
    note: string | null,
  ) => Promise<DoctorRoleApplication>
  clearReviewers: () => void
  clearError: () => void
}

type ApiError = {
  response?: { data?: { detail?: string } }
  message?: string
}

const normalizeError = (error: unknown, fallback: string) => {
  if (!error || typeof error !== 'object') return fallback
  const apiError = error as ApiError
  return apiError.response?.data?.detail || apiError.message || fallback
}

export const useDoctorRoleApplicationsStore = create<DoctorRoleApplicationsState>((set, get) => ({
  specialties: [],
  reviewers: [],
  mine: [],
  inbox: [],
  isLoading: false,
  isSubmitting: false,
  error: null,

  fetchSpecialties: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<string[]>('/doctor-role-applications/specialties')
      set({ specialties: data, isLoading: false })
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось загрузить специализации'), isLoading: false })
    }
  },

  fetchReviewers: async (specialty) => {
    const normalized = specialty.trim()
    if (normalized.length < 2) {
      set({ reviewers: [] })
      return
    }
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<DoctorRoleReviewerCandidate[]>('/doctor-role-applications/reviewers', {
        params: { specialty: normalized },
      })
      set({ reviewers: data, isLoading: false })
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось загрузить проверяющих'), reviewers: [], isLoading: false })
    }
  },

  fetchMine: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<DoctorRoleApplication[]>('/doctor-role-applications/mine')
      set({ mine: data, isLoading: false })
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось загрузить заявки'), isLoading: false })
    }
  },

  fetchInbox: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<DoctorRoleApplication[]>('/doctor-role-applications/inbox')
      set({ inbox: data, isLoading: false })
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось загрузить входящие заявки'), isLoading: false })
    }
  },

  createApplication: async (specialty, reviewerUserIds) => {
    set({ isSubmitting: true, error: null })
    try {
      const { data } = await api.post<DoctorRoleApplication>('/doctor-role-applications', {
        specialty: specialty.trim(),
        reviewer_user_ids: reviewerUserIds,
      })
      set({ mine: [data, ...get().mine.filter((item) => item.id !== data.id)], isSubmitting: false })
      return data
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось отправить заявку'), isSubmitting: false })
      throw error
    }
  },

  reviewApplication: async (applicationId, decision, note) => {
    set({ isSubmitting: true, error: null })
    try {
      const { data } = await api.post<DoctorRoleApplication>(
        `/doctor-role-applications/${applicationId}/review`,
        { decision, note },
      )
      set({
        inbox: get().inbox.filter((item) => item.id !== applicationId),
        isSubmitting: false,
      })
      return data
    } catch (error) {
      set({ error: normalizeError(error, 'Не удалось сохранить решение'), isSubmitting: false })
      throw error
    }
  },

  clearReviewers: () => set({ reviewers: [] }),
  clearError: () => set({ error: null }),
}))
