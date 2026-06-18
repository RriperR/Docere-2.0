import { create } from 'zustand'
import api from '../api/api'

export type PatientAccessContext = 'own_confirmed' | 'created' | 'shared'

export interface Patient {
  id: string
  fio: string
  firstName: string
  lastName: string
  middleName?: string
  birthday?: string
  email?: string
  phone?: string
  status: string
  accessContext: PatientAccessContext
  lastVisit?: string
  recordCount: number
}

export interface PractitionerInfo {
  id: string
  user_id: string | null
  full_name: string
  specialty?: string
  organization?: string
  position?: string
  email?: string
  phone?: string
  status: string
}

export interface FileAttachment {
  id: string
  record_id: string
  comment_id?: string
  uploaded_by_user_id: string
  category: string
  filename?: string
  storage_key: string
  mime_type: string
  size_bytes: number
  uploaded_at: string
}

export interface RecordComment {
  id: string
  record_id: string
  author_user_id: string
  author_fio: string
  author_role: string
  body: string
  attachments: FileAttachment[]
  created_at: string
}

export interface PatientRecordSummary {
  id: string
  status: string
  recordType: string
  eventDate: string
  title?: string
  appointmentLocation?: string
  clinicalSummary?: string
  practitioner?: PractitionerInfo
  commentsCount: number
  attachmentsCount: number
  createdAt: string
  updatedAt: string
}

export interface PatientRecordDetail extends PatientRecordSummary {
  creatorUserId: string
  authorPractitionerPassportId?: string
  patientPassportId?: string
  payloadJson: Record<string, unknown>
  comments: RecordComment[]
  attachments: FileAttachment[]
}

export interface CreatePatientRecordPayload {
  record_type: string
  event_date: string
  title?: string
  appointment_location?: string
  clinical_summary?: string
  payload_json: Record<string, unknown>
  author_practitioner_passport_id?: string
  author_practitioner_full_name?: string
  author_practitioner_specialty?: string
  author_practitioner_organization?: string
  author_practitioner_position?: string
  author_practitioner_email?: string
  author_practitioner_phone?: string
}

interface BackendPatient {
  id: string
  fio: string
  date_of_birth: string | null
  email: string | null
  phone: string | null
  status: string
  access_context: PatientAccessContext
  record_count: number
  last_record_date: string | null
}

interface BackendPractitioner {
  id: string
  user_id: string | null
  full_name: string
  specialty: string | null
  organization: string | null
  position: string | null
  email: string | null
  phone: string | null
  status: string
}

interface BackendAttachment {
  id: string
  record_id: string
  comment_id: string | null
  uploaded_by_user_id: string
  category: string
  filename: string | null
  storage_key: string
  mime_type: string
  size_bytes: number
  uploaded_at: string
}

interface BackendComment {
  id: string
  record_id: string
  author_user_id: string
  author_fio: string
  author_role: string
  body: string
  attachments: BackendAttachment[]
  created_at: string
}

interface BackendRecordSummary {
  id: string
  status: string
  record_type: string
  event_date: string
  title: string | null
  appointment_location: string | null
  clinical_summary: string | null
  author_practitioner_passport: BackendPractitioner | null
  comments_count: number
  attachments_count: number
  created_at: string
  updated_at: string
}

interface BackendRecordDetail extends BackendRecordSummary {
  creator_user_id: string
  author_practitioner_passport_id: string | null
  patient_passport_id: string | null
  payload_json: Record<string, unknown>
  comments: BackendComment[]
  attachments: BackendAttachment[]
}

interface PatientsState {
  patients: Patient[]
  filteredPatients: Patient[]
  currentPatient: Patient | null
  patientRecords: PatientRecordSummary[]
  activeRecord: PatientRecordDetail | null
  isLoading: boolean
  error: string | null

  fetchPatients: () => Promise<void>
  createPatient: (payload: { fio: string; email?: string; phone?: string; date_of_birth?: string }) => Promise<void>
  fetchPatientById: (id: string) => Promise<void>
  fetchPatientRecords: (id: string) => Promise<void>
  fetchRecordDetail: (recordId: string) => Promise<PatientRecordDetail>
  createPatientRecord: (patientId: string, payload: CreatePatientRecordPayload) => Promise<string>
  uploadRecordAttachment: (recordId: string, file: File) => Promise<void>
  addRecordComment: (recordId: string, body: string) => Promise<void>
  uploadCommentAttachment: (recordId: string, commentId: string, file: File) => Promise<void>
  downloadAttachment: (recordId: string, attachmentId: string, filename: string) => Promise<void>
  clearActiveRecord: () => void
  searchPatients: (query: string) => void
  filterPatientsByDate: (startDate?: string, endDate?: string) => void
}

const splitFio = (fio: string): { firstName: string; lastName: string; middleName?: string } => {
  const parts = fio
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0)

  const [lastName = '', firstName = '', ...rest] = parts
  return {
    firstName,
    lastName,
    middleName: rest.length > 0 ? rest.join(' ') : undefined,
  }
}

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
  message?: string
}

const normalizeError = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) {
    return fallback
  }

  const apiError = error as ApiError
  return apiError.response?.data?.detail || apiError.message || fallback
}

const mapPractitioner = (p: BackendPractitioner | null): PractitionerInfo | undefined => {
  if (!p) {
    return undefined
  }

  return {
    id: p.id,
    user_id: p.user_id,
    full_name: p.full_name,
    specialty: p.specialty ?? undefined,
    organization: p.organization ?? undefined,
    position: p.position ?? undefined,
    email: p.email ?? undefined,
    phone: p.phone ?? undefined,
    status: p.status,
  }
}

const mapPatient = (p: BackendPatient): Patient => {
  const fio = splitFio(p.fio)
  return {
    id: p.id,
    fio: p.fio,
    firstName: fio.firstName,
    lastName: fio.lastName,
    middleName: fio.middleName,
    birthday: p.date_of_birth ?? undefined,
    email: p.email ?? undefined,
    phone: p.phone ?? undefined,
    status: p.status,
    accessContext: p.access_context,
    lastVisit: p.last_record_date ?? undefined,
    recordCount: p.record_count,
  }
}

const mapRecordSummary = (r: BackendRecordSummary): PatientRecordSummary => ({
  id: r.id,
  status: r.status,
  recordType: r.record_type,
  eventDate: r.event_date,
  title: r.title ?? undefined,
  appointmentLocation: r.appointment_location ?? undefined,
  clinicalSummary: r.clinical_summary ?? undefined,
  practitioner: mapPractitioner(r.author_practitioner_passport),
  commentsCount: r.comments_count,
  attachmentsCount: r.attachments_count,
  createdAt: r.created_at,
  updatedAt: r.updated_at,
})

const mapAttachment = (attachment: BackendAttachment): FileAttachment => ({
  id: attachment.id,
  record_id: attachment.record_id,
  comment_id: attachment.comment_id ?? undefined,
  uploaded_by_user_id: attachment.uploaded_by_user_id,
  category: attachment.category,
  filename: attachment.filename ?? undefined,
  storage_key: attachment.storage_key,
  mime_type: attachment.mime_type,
  size_bytes: attachment.size_bytes,
  uploaded_at: attachment.uploaded_at,
})

const mapRecordDetail = (r: BackendRecordDetail): PatientRecordDetail => ({
  ...mapRecordSummary(r),
  creatorUserId: r.creator_user_id,
  authorPractitionerPassportId: r.author_practitioner_passport_id ?? undefined,
  patientPassportId: r.patient_passport_id ?? undefined,
  payloadJson: r.payload_json,
  comments: r.comments.map((comment) => ({
    id: comment.id,
    record_id: comment.record_id,
    author_user_id: comment.author_user_id,
    author_fio: comment.author_fio,
    author_role: comment.author_role,
    body: comment.body,
    attachments: comment.attachments.map(mapAttachment),
    created_at: comment.created_at,
  })),
  attachments: r.attachments.map(mapAttachment),
})

export const usePatientsStore = create<PatientsState>((set, get) => ({
  patients: [],
  filteredPatients: [],
  currentPatient: null,
  patientRecords: [],
  activeRecord: null,
  isLoading: false,
  error: null,

  fetchPatients: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<BackendPatient[]>('/patients')
      const patients = data.map(mapPatient)
      set({ patients, filteredPatients: patients, isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось загрузить пациентов'),
        isLoading: false,
      })
    }
  },

  createPatient: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      await api.post('/patients', payload)
      await get().fetchPatients()
      set({ isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось создать пациента'),
        isLoading: false,
      })
      throw error
    }
  },

  fetchPatientById: async (id) => {
    set({ isLoading: true, error: null, currentPatient: null })
    try {
      const { data } = await api.get<BackendPatient>(`/patients/${id}`)
      set({ currentPatient: mapPatient(data), isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось загрузить карточку пациента'),
        isLoading: false,
      })
    }
  },

  fetchPatientRecords: async (patientId) => {
    set({ isLoading: true, error: null, patientRecords: [], activeRecord: null })
    try {
      const { data } = await api.get<BackendRecordSummary[]>(`/patients/${patientId}/records`)
      set({ patientRecords: data.map(mapRecordSummary), isLoading: false })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось загрузить записи пациента'),
        isLoading: false,
      })
    }
  },

  fetchRecordDetail: async (recordId) => {
    const { data } = await api.get<BackendRecordDetail>(`/records/${recordId}`)
    const record = mapRecordDetail(data)
    set({ activeRecord: record })
    return record
  },

  createPatientRecord: async (patientId, payload) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<BackendRecordDetail>('/records', {
        patient_passport_id: patientId,
        ...payload,
      })
      await get().fetchPatientRecords(patientId)
      const patients = get().patients.map((patient) =>
        patient.id === patientId
          ? {
              ...patient,
              recordCount: patient.recordCount + 1,
              lastVisit: payload.event_date,
            }
          : patient,
      )
      set({
        patients,
        filteredPatients: patients,
        isLoading: false,
      })
      return data.id
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось создать запись'),
        isLoading: false,
      })
      throw error
    }
  },

  uploadRecordAttachment: async (recordId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post(`/records/${recordId}/attachments`, formData)
      if (get().activeRecord?.id === recordId) {
        await get().fetchRecordDetail(recordId)
      }
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось загрузить файл') })
      throw error
    }
  },

  addRecordComment: async (recordId, body) => {
    set({ isLoading: true, error: null })
    try {
      await api.post(`/records/${recordId}/comments`, { body })
      const currentActiveRecord = get().activeRecord
      if (currentActiveRecord?.id === recordId) {
        await get().fetchRecordDetail(recordId)
      }
      set({
        patientRecords: get().patientRecords.map((record) =>
          record.id === recordId
            ? { ...record, commentsCount: record.commentsCount + 1 }
            : record,
        ),
        isLoading: false,
      })
    } catch (error: unknown) {
      set({
        error: normalizeError(error, 'Не удалось добавить комментарий'),
        isLoading: false,
      })
      throw error
    }
  },

  uploadCommentAttachment: async (recordId, commentId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post(`/records/${recordId}/comments/${commentId}/attachments`, formData)
      if (get().activeRecord?.id === recordId) {
        await get().fetchRecordDetail(recordId)
      }
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось загрузить файл') })
      throw error
    }
  },

  downloadAttachment: async (recordId, attachmentId, filename) => {
    try {
      const { data } = await api.get<Blob>(`/records/${recordId}/attachments/${attachmentId}`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error: unknown) {
      set({ error: normalizeError(error, 'Не удалось скачать файл') })
      throw error
    }
  },

  clearActiveRecord: () => set({ activeRecord: null }),

  searchPatients: (query) => {
    const patients = get().patients
    if (!query.trim()) {
      set({ filteredPatients: patients })
      return
    }

    const q = query.toLowerCase()
    set({
      filteredPatients: patients.filter(
        (patient) =>
          patient.fio.toLowerCase().includes(q) ||
          (patient.email ?? '').toLowerCase().includes(q) ||
          (patient.phone ?? '').toLowerCase().includes(q),
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
      filteredPatients: patients.filter((patient) => {
        if (!patient.lastVisit) return false
        if (startDate && patient.lastVisit < startDate) return false
        if (endDate && patient.lastVisit > endDate) return false
        return true
      }),
    })
  },
}))
