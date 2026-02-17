// src/stores/patientStore.ts
import { create } from 'zustand'
import api from '../api/api'

export interface Patient {
  id: string
  lastName: string
  firstName: string
  middleName?: string
  birthday?: string
  email?: string
  phone?: string
  photoUrl?: string
  lastVisit?: string
  recordCount?: number
}

export interface LabFile {
  id: string
  file: string
  file_type: string
}

export interface DoctorInfo {
  full_name: string
  photo: string
  specialization: string
}

export interface PatientRecord {
  id: string
  visit_date?: string
  created_at?: string
  appointment_location?: string
  notes: string
  doctor?: DoctorInfo
  lab_files?: LabFile[]
  versions?: {
    id: string
    date: string
    changedBy: string
  }[]
}

interface PatientsState {
  patients: Patient[]
  filteredPatients: Patient[]
  currentPatient: Patient | null
  patientRecords: PatientRecord[]
  isLoading: boolean
  error: string | null

  fetchPatients: () => Promise<void>
  fetchPatientById: (id: string) => Promise<void>
  fetchPatientRecords: (id: string) => Promise<void>
  createPatientRecord: (patientId: string, form: FormData) => Promise<void>
  updatePatientRecord: (patientId: string, recordId: string, form: FormData) => Promise<void>
  shareRecords: (patientId: string, toEmail: string, recordIds: string[]) => Promise<void>
  searchPatients: (query: string) => void
  filterPatientsByDate: (startDate?: string, endDate?: string) => void
}

export const usePatientsStore = create<PatientsState>((set, get) => ({
  patients: [],
  filteredPatients: [],
  currentPatient: null,
  patientRecords: [],
  isLoading: false,
  error: null,

  fetchPatients: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<any[]>('/patients/')
      const patients: Patient[] = data.map(p => ({
        id: String(p.id),
        firstName: p.first_name,
        lastName: p.last_name,
        middleName: p.middle_name ?? undefined,
        birthday: p.birthday,
        email: p.email ?? undefined,
        phone: p.phone ?? undefined,
        photoUrl: p.photo_url ?? undefined,
        lastVisit: p.last_visit ?? undefined,
        recordCount: p.record_count ?? 0,
      }))
      set({ patients, filteredPatients: patients, isLoading: false })
    } catch (e: any) {
      set({
        error: e.response?.data?.detail || 'Failed to fetch patients',
        isLoading: false,
      })
    }
  },

  fetchPatientById: async id => {
    set({ isLoading: true, error: null, currentPatient: null })
    try {
      const { data: p } = await api.get<any>(`/patients/${id}/`)
      const patient: Patient = {
        id: String(p.id),
        firstName: p.first_name,
        lastName: p.last_name,
        middleName: p.middle_name ?? undefined,
        birthday: p.birthday,
        email: p.email ?? undefined,
        phone: p.phone ?? undefined,
        photoUrl: p.photo_url ?? undefined,
        lastVisit: p.last_visit ?? undefined,
        recordCount: p.record_count ?? 0,
      }
      set({ currentPatient: patient, isLoading: false })
    } catch (e: any) {
      set({
        error: e.response?.data?.detail || 'Failed to fetch patient',
        isLoading: false,
      })
    }
  },

  fetchPatientRecords: async patientId => {
    set({ isLoading: true, error: null, patientRecords: [] })
    try {
      const { data } = await api.get<any[]>(`/patients/${patientId}/records/`)
      const recs: PatientRecord[] = data.map(r => ({
        id: String(r.id),
        visit_date: r.visit_date,
        created_at: r.created_at,
        appointment_location: r.appointment_location,
        notes: r.notes,
        doctor: r.doctor ?? undefined,
        lab_files: r.lab_files ?? [],
        versions: r.versions ?? [],
      }))
      set({ patientRecords: recs, isLoading: false })
    } catch (e: any) {
      set({
        error: e.response?.data?.detail || 'Failed to fetch records',
        isLoading: false,
      })
    }
  },

  createPatientRecord: async (patientId, form) => {
    set({ isLoading: true, error: null })
    try {
      const { data: rec } = await api.post<any>(
        `/patients/${patientId}/records/`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      set(state => ({
        patientRecords: [rec, ...state.patientRecords],
        currentPatient: state.currentPatient
          ? {
              ...state.currentPatient,
              lastVisit: rec.visit_date ?? state.currentPatient.lastVisit,
            }
          : state.currentPatient,
      }))
    } catch (e: any) {
      set({ error: e.response?.data || 'Failed to create record' })
    } finally {
      set({ isLoading: false })
    }
  },

  updatePatientRecord: async (patientId, recordId, form) => {
    set({ isLoading: true, error: null })
    try {
      const { data: rec } = await api.patch<any>(
        `/patients/${patientId}/records/${recordId}/`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      set(state => ({
        patientRecords: state.patientRecords.map(r =>
          r.id === String(rec.id) ? rec : r
        ),
      }))
    } catch (e: any) {
      set({ error: e.response?.data || 'Failed to update record' })
    } finally {
      set({ isLoading: false })
    }
  },

  // Новый экшен: шарим несколько записей за раз
  shareRecords: async (patientId, toEmail, recordIds) => {
    set({ isLoading: true, error: null })
    try {
      await api.post('/share-requests/', {
        patient_id: Number(patientId),
        to_email: toEmail,
        record_ids: recordIds,
      })
    } catch (e: any) {
      set({ error: e.response?.data || 'Failed to share records' })
      throw e
    } finally {
      set({ isLoading: false })
    }
  },

  searchPatients: query => {
    const patients = get().patients
    if (!query.trim()) {
      set({ filteredPatients: patients })
      return
    }
    const q = query.toLowerCase()
    set({
      filteredPatients: patients.filter(
        p =>
          p.firstName.toLowerCase().includes(q) ||
          p.lastName.toLowerCase().includes(q) ||
          (p.email ?? '').toLowerCase().includes(q)
      ),
    })
  },

  filterPatientsByDate: (startDate, endDate) => {
    const patients = get().patients
    if (!startDate && !endDate) {
      set({ filteredPatients: patients })
      return
    }
    set({
      filteredPatients: patients.filter(p => {
        if (!p.lastVisit) return false
        if (startDate && p.lastVisit < startDate) return false
        if (endDate && p.lastVisit > endDate) return false
        return true
      }),
    })
  },
}))
