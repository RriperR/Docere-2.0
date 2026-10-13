import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../../api/api'
import { useAuthStore } from '../../stores/authStore'

export interface ImportContextPatient { id: string; fio: string; date_of_birth: string | null }

/** A URL is only a hint: the patient API checks access before any field can use it. */
export function usePatientImportContext() {
  const [params, setParams] = useSearchParams()
  const patientId = params.get('patient') ?? ''
  const userId = useAuthStore(state => state.user?.id)
  const [patient, setPatient] = useState<ImportContextPatient | null>(null)
  const [verifiedUserId, setVerifiedUserId] = useState<string | undefined>(undefined)
  const [error, setError] = useState(false)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    setPatient(null); setError(false)
    if (!patientId) return
    const controller = new AbortController()
    void api.get<ImportContextPatient>(`/patients/${encodeURIComponent(patientId)}`, { signal: controller.signal })
      .then(({ data }) => { if (controller.signal.aborted) return; if (data.id !== patientId) throw new Error('Карточка недоступна'); setPatient(data); setVerifiedUserId(userId) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [patientId, userId, revision])
  return {
    patientId, patient: patient?.id === patientId && verifiedUserId === userId ? patient : null, error,
    query: patientId ? `?patient=${encodeURIComponent(patientId)}` : '',
    retry: () => setRevision(value => value + 1),
    clear: () => { const next = new URLSearchParams(params); next.delete('patient'); setParams(next, { replace: true }) },
  }
}

