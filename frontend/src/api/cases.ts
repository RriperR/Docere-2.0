import axios from 'axios'
import api from './api'

export interface CaseMember { user_id: string; status: string; name: string; read_sequence: number }
export interface ClinicalCase {
  id: string; patient_id: string; coordinator_id: string; title: string; question: string
  status: 'draft' | 'active' | 'closed'; version: number; sequence: number
  record_ids: string[]; members: CaseMember[]; created_at: string; previous_case_id: string | null
  published_record_id: string | null
}
export interface CaseView {
  id: string; status: string; membership_status: string; coordinator_id: string; coordinator_name: string
  material_count: number; accessible: boolean; case: ClinicalCase | null; invitation_terms: string
}
export interface Page<T> { items: T[]; total: number }
export interface Material {
  id: string; title: string | null; clinical_summary: string | null; record_type: string
  event_date: string; status: string
}
export interface Doctor { id: string; name: string; email: string }
export interface PatientOption { id: string; fio: string }

export function caseError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.detail ?? error.response?.data?.error?.message
    if (typeof message === 'string') return message
    if (error.response?.status === 409) return 'Случай изменился. Обновите данные.'
  }
  return 'Не удалось выполнить действие. Повторите попытку.'
}
export const caseApi = {
  list: async (scope: string, status: string, offset: number) =>
    (await api.get<Page<CaseView>>('/cases', { params: { scope, status: status || undefined, offset, limit: 20 } })).data,
  get: async (id: string) => (await api.get<CaseView>(`/cases/${id}`)).data,
  post: async (id: string, path: string, payload?: unknown) =>
    (await api.post<CaseView>(`/cases/${id}/${path}`, payload)).data,
  doctors: async (query: string) => (await api.get<Doctor[]>('/cases/doctors', { params: { query } })).data,
  patients: async (q: string) => (await api.get<PatientOption[]>('/patients/search', { params: { q, limit: 10 } })).data,
  available: async (patientId: string, query: string, offset: number) =>
    (await api.get<Page<Material>>(`/cases/patients/${patientId}/available-records`,
      { params: { query, offset, limit: 20 } })).data,
  create: async (payload: unknown) => (await api.post<CaseView>('/cases', payload)).data,
}
