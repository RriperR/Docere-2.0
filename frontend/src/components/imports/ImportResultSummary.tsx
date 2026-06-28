import { Link } from 'react-router-dom'

import { type ImportResolvedPatient } from '../../stores/uploadStore'
import { Card } from '../common/Card'

type ImportResultSummaryProps = {
  patients: ImportResolvedPatient[]
}

export const ImportResultSummary = ({ patients }: ImportResultSummaryProps) => {
  if (patients.length === 0) return null

  return (
    <Card title="Результат импорта" accent="success">
      <div className="space-y-3">
        {patients.map((patient) => {
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
                <p className="font-medium text-gray-900">{label}</p>
                <p className="text-sm text-gray-500">
                  Записей создано: {patient.record_ids.length}; групп пропущено:{' '}
                  {patient.record_groups.filter((group) => group.action === 'skip').length}
                </p>
              </div>
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
