import { useEffect, useState } from 'react'
import api from '../../api/api'
import { useAuthStore } from '../../stores/authStore'
import { Link } from 'react-router-dom'

import { type ImportResolvedPatient } from '../../stores/uploadStore'
import { Card } from '../common/Card'

type ImportResultSummaryProps = {
  patients: ImportResolvedPatient[]
}

export const ImportResultSummary = ({ patients }: ImportResultSummaryProps) => {
  const [names, setNames] = useState<Record<string, string>>({})
  const user = useAuthStore(state => state.user)
  useEffect(() => {
    const controller = new AbortController()
    setNames({})
    for (const patient of patients) {
      if (!patient.patient_id) continue
      const id = patient.patient_id
      void api.get<{ id: string; fio: string }>(`/patients/${encodeURIComponent(id)}`, { signal: controller.signal })
        .then(({ data }) => { if (!controller.signal.aborted && data.id === id) setNames(current => ({ ...current, [id]: data.fio })) })
        .catch(() => undefined)
    }
    return () => controller.abort()
  }, [patients, user?.id])
  if (patients.length === 0) return null

  return (
    <Card title="Результат импорта" accent="success">
      <div className="space-y-3">
        {patients.map((patient, index) => {
          const firstRecordId = patient.record_ids[0]
          const target = patient.patient_id
            ? `/patients/${patient.patient_id}${firstRecordId ? `#record-${firstRecordId}` : ''}`
            : null
          const label = patient.action === 'skip'
            ? 'Пациент пропущен'
            : patient.action === 'create'
              ? 'Создана карточка пациента'
              : 'Использована существующая карточка'

          return (
            <div
              key={patient.candidate_id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-100 px-4 py-3"
            >
              <div>
                {patient.patient_id && <h3 className="font-semibold text-gray-900">{names[patient.patient_id] ?? `Карточка пациента ${index + 1}`}</h3>}
                <p className="font-medium text-gray-900">{label}</p>
                <p className="text-sm text-gray-500">
                  Записей создано: {patient.record_ids.length}; групп пропущено:{' '}
                  {patient.record_groups.filter((group) => group.action === 'skip').length}
                </p>
              </div>
              {patient.patient_id && patient.record_ids.length > 0 && (
                <ul className="w-full space-y-1 text-sm">
                  {patient.record_ids.map((recordId, recordIndex) => (
                    <li key={recordId}>
                      <Link className="text-primary-700 hover:underline" to={`/patients/${patient.patient_id}#record-${recordId}`}>
                        Открыть запись {recordIndex + 1}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {user?.role === 'doctor' && patient.patient_id && patient.record_ids.length > 0 && <Link className="text-sm font-semibold text-primary-700 hover:underline" to={`/cases/new?patient=${patient.patient_id}${patient.record_ids.length <= 100 ? patient.record_ids.map(id => `&record=${encodeURIComponent(id)}`).join('') : ''}`}>Обсудить {patient.record_ids.length <= 100 ? `эти записи (${patient.record_ids.length})` : 'выбранные записи'} в клиническом случае</Link>}
              {target && (
                <Link className="text-sm font-medium text-primary-700 hover:underline" to={target}>
                  Открыть медицинскую историю
                </Link>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
