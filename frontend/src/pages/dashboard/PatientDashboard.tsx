import React, { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Calendar, ChevronRight, FileText, Stethoscope } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

const typeColors: Record<string, string> = {
  consultation_result: 'bg-accent-100 text-accent-700',
  exam_result: 'bg-secondary-100 text-secondary-700',
  lab_result: 'bg-warning-100 text-warning-700',
  other: 'bg-gray-100 text-gray-600',
}

const typeLabel: Record<string, string> = {
  consultation_result: 'Консультация',
  exam_result: 'Обследование',
  lab_result: 'Лаборатория',
  other: 'Другое',
}

const PatientDashboard: React.FC = () => {
  const { user } = useAuthStore()
  const { fetchPatients, patients, currentPatient, patientRecords, fetchPatientRecords } =
    usePatientsStore()

  const patient = currentPatient ?? patients[0] ?? null

  useEffect(() => {
    if (user?.role === 'patient') void fetchPatients()
  }, [user?.role, fetchPatients])

  useEffect(() => {
    if (patient?.id) void fetchPatientRecords(patient.id)
  }, [patient?.id, fetchPatientRecords])

  const recentRecords = useMemo(() => patientRecords.slice(0, 5), [patientRecords])

  const lastRecord = recentRecords[0]
  const lastVisitLabel = patient?.lastVisit
    ? `Последний визит: ${format(new Date(patient.lastVisit), 'dd.MM.yyyy')}`
    : 'Записей пока нет'

  const displayName = patient
    ? patient.fio
    : user
      ? `${user.first_name} ${user.last_name}`
      : 'Личный кабинет'

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white p-6 shadow-card"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{displayName}</h1>
            <p className="mt-1 text-sm text-gray-500">{lastVisitLabel}</p>
          </div>
          {patient?.id && (
            <Link to={`/patients/${patient.id}`}>
              <Button size="sm">Открыть карточку</Button>
            </Link>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-primary-50 p-4">
            <p className="text-3xl font-bold text-primary-600">{patientRecords.length}</p>
            <p className="mt-1 text-sm text-gray-600">Медицинских записей</p>
          </div>
          <div className="rounded-lg bg-secondary-50 p-4">
            <p className="text-3xl font-bold text-secondary-600">
              {patientRecords.filter((r) => r.recordType === 'consultation_result').length}
            </p>
            <p className="mt-1 text-sm text-gray-600">Консультаций</p>
          </div>
          <div className="rounded-lg bg-accent-50 p-4 col-span-2 sm:col-span-1">
            <p className="text-3xl font-bold text-accent-600">
              {patientRecords.filter((r) => r.recordType === 'lab_result').length}
            </p>
            <p className="mt-1 text-sm text-gray-600">Результатов лабораторий</p>
          </div>
        </div>
      </motion.div>

      {lastRecord && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="rounded-xl border border-primary-100 bg-primary-50 p-5"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary-500">
                Последняя запись
              </p>
              <h3 className="mt-1 text-base font-semibold text-gray-900">
                {lastRecord.title || 'Медицинская запись'}
              </h3>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-gray-500">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  {format(new Date(lastRecord.eventDate), 'dd.MM.yyyy')}
                </span>
                {lastRecord.practitioner?.full_name && (
                  <span className="flex items-center gap-1">
                    <Stethoscope className="h-3.5 w-3.5" />
                    {lastRecord.practitioner.full_name}
                  </span>
                )}
              </div>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${typeColors[lastRecord.recordType] ?? 'bg-gray-100 text-gray-600'}`}>
              {typeLabel[lastRecord.recordType] ?? lastRecord.recordType}
            </span>
          </div>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white shadow-card"
      >
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">История наблюдений</h2>
          <p className="text-xs text-gray-500 mt-0.5">Хронология медицинских событий</p>
        </div>

        {recentRecords.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <FileText className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-gray-900">Записей пока нет</p>
            <p className="mt-1 text-xs text-gray-500">Ваши медицинские записи появятся здесь</p>
          </div>
        ) : (
          <div className="relative px-6 py-4">
            <div className="absolute left-[2.35rem] top-8 bottom-4 w-px bg-gray-100" />
            <div className="space-y-4">
              {recentRecords.map((record, i) => (
                <Link
                  key={record.id}
                  to={patient ? `/patients/${patient.id}` : '/patients'}
                  className="group relative flex items-start gap-4"
                >
                  <div className={`relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-2 ring-white ${i === 0 ? 'bg-primary-500' : 'bg-gray-200'}`}>
                    <div className={`h-2 w-2 rounded-full ${i === 0 ? 'bg-white' : 'bg-gray-400'}`} />
                  </div>
                  <div className="min-w-0 flex-1 rounded-lg border border-transparent bg-gray-50 p-3 transition-all group-hover:border-primary-100 group-hover:bg-primary-50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-gray-900 group-hover:text-primary-700">
                          {record.title || 'Медицинская запись'}
                        </p>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {format(new Date(record.eventDate), 'dd.MM.yyyy')}
                          </span>
                          {record.practitioner?.full_name && (
                            <span className="flex items-center gap-1">
                              <Stethoscope className="h-3 w-3" />
                              {record.practitioner.full_name}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${typeColors[record.recordType] ?? 'bg-gray-100 text-gray-600'}`}>
                          {typeLabel[record.recordType] ?? record.recordType}
                        </span>
                        <ChevronRight className="h-3.5 w-3.5 text-gray-300 group-hover:text-primary-400 transition-colors" />
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {patient?.id && recentRecords.length > 0 && (
          <div className="border-t border-gray-100 px-6 py-3">
            <Link
              to={`/patients/${patient.id}`}
              className="text-sm font-medium text-primary-600 hover:text-primary-700"
            >
              Открыть полную карточку →
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  )
}

export default PatientDashboard
