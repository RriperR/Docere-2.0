// src/pages/shares/ShareRequestsPage.tsx
import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { Card } from '../../components/common/Card'
import { Button } from '../../components/common/Button'
import { X, FileText } from 'lucide-react'
import api from '../../api/api'

import { useShareRequestsStore } from '../../stores/shareRequestsStore'
import type { PatientRecord, DoctorInfo } from '../../stores/patientsStore'

export function ShareRequestsPage() {
  const { requests, isLoading, error, fetchAll, respond } = useShareRequestsStore()
  const [modalRecord, setModalRecord] = useState<PatientRecord | null>(null)

  useEffect(() => {
    // Подгружаем все запросы
    fetchAll()
  }, [fetchAll])

  if (isLoading) return <p>Загрузка шарингов…</p>
  if (error)     return <p className="text-red-600">{error}</p>
  if (!requests.length) return <p>Нет запросов на шаринг.</p>

  return (
    <>
      <div className="space-y-6">
        {requests.map(req => (
          <Card key={req.id} className="p-6">
            <h2 className="text-lg font-medium mb-4">
              От: {req.from_user_fullname} → {req.to_email} <br/>
              Пациент: {req.patient_name} — {format(new Date(req.created_at), 'dd.MM.yyyy, HH:mm')}<br/>
              Статус: <strong>{req.status}</strong>
            </h2>

            <ul className="space-y-4">
              {req.shares.map(s => (
                <li key={s.id} className="flex items-start justify-between">
                  <div>
                    <p>
                      <strong>Запись #{s.record_id}</strong> — статус: {s.status}
                    </p>
                    <p className="text-sm text-gray-600 mt-1">
                      Дата: {s.visit_date ?? '—'}
                    </p>
                  </div>
                  <div className="flex flex-col items-end space-y-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        // Загрузим конкретную запись
                        const { data } = await api.get<PatientRecord>(
                          `/patients/${req.patient}/records/${s.record_id}/`
                        )
                        setModalRecord(data)
                      }}
                    >
                      Открыть
                    </Button>
                    <div className="flex space-x-2">
                      <Button
                        size="sm"
                        onClick={() => respond(req.id, s.id, 'accept')}
                        disabled={s.status !== 'pending'}
                      >
                        Принять
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => respond(req.id, s.id, 'decline')}
                        disabled={s.status !== 'pending'}
                      >
                        Отклонить
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      {modalRecord && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full overflow-auto max-h-[90vh]">
            <div className="flex justify-end p-4">
              <button onClick={() => setModalRecord(null)}>
                <X className="h-5 w-5 text-gray-600 hover:text-gray-800" />
              </button>
            </div>
            <RecordView record={modalRecord} />
          </div>
        </div>
      )}
    </>
  )
}

// View-only из PatientDetailsPage
function RecordView({ record }: { record: PatientRecord }) {
  const isImage = (f: string) => /\.(jpe?g|png|gif)$/i.test(f)
  const doc = record.doctor as DoctorInfo|undefined
  const dateLabel = record.visit_date
    ? format(new Date(record.visit_date), 'd MMMM yyyy')
    : '—'

  return (
    <div className="space-y-4 p-6">
      <div className="grid grid-cols-[auto_1fr_auto_auto]
                      items-center bg-gray-50 px-6 py-2 text-sm text-gray-600 rounded-t-lg">
        <div>{dateLabel}</div>
        <div className="text-center">Комментарий / Заключение</div>
        <div className="text-right">Лабораторные данные</div>
      </div>
      <div className="grid grid-cols-[auto_auto_2fr_1fr] gap-6 p-6">
        {/* Доктор */}
        <div className="flex flex-col items-center space-y-1">
          <img src={doc?.photo||'/images/doctor.png'} className="h-10 w-10 rounded-full" />
          <p className="font-medium">{doc?.full_name||'Не назначен'}</p>
        </div>
        {/* Локация */}
        <div className="flex flex-col items-center space-y-1">
          <img src="/images/hospital.png" className="h-10 w-10 rounded-full" />
          <p className="font-medium">{record.appointment_location||'—'}</p>
        </div>
        {/* Заметки */}
        <div className="text-gray-800 whitespace-pre-line">
          {record.notes||'—'}
        </div>
        {/* Файлы */}
        <div className="flex flex-wrap gap-3">
          {(record.lab_files||[]).map(f =>
            isImage(f.file) ? (
              <a key={f.id} href={f.file} target="_blank" rel="noopener noreferrer"
                 className="h-24 w-24 border rounded overflow-hidden">
                <img src={f.file} className="h-full w-full object-cover"/>
              </a>
            ) : (
              <a key={f.id} href={f.file} target="_blank" rel="noopener noreferrer"
                 className="h-24 w-24 flex flex-col items-center justify-center
                            bg-gray-50 border rounded text-primary-600">
                <FileText className="h-8 w-8"/><span className="text-[10px] mt-1">PDF</span>
              </a>
            )
          )}
        </div>
      </div>
    </div>
  )
}
