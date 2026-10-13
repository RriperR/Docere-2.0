import { useCallback, useEffect, useState } from 'react'
import api from '../../api/api'
import type { DoctorRoleApplication } from '../../stores/doctorRoleApplicationsStore'

/** Load application state separately from reviewer searches and their errors. */
export function useMyDoctorApplications() {
  const [mine, setMine] = useState<DoctorRoleApplication[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [revision, setRevision] = useState(0)
  const retry = useCallback(() => setRevision(value => value + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    void api.get<DoctorRoleApplication[]>('/doctor-role-applications/mine', { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) setMine(data) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [revision])
  const current = mine.find(item => item.status === 'pending')
    ?? [...mine].sort((left, right) => right.created_at.localeCompare(left.created_at))[0]
    ?? null
  return { mine, current, loading, error, retry }
}
