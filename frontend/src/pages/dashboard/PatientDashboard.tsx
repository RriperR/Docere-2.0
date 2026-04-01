import React, { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Calendar, FileText, Stethoscope } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

const PatientDashboard: React.FC = () => {
  const { user } = useAuthStore()
  const {
    fetchPatients,
    patients,
    currentPatient,
    patientRecords,
    fetchPatientRecords,
  } = usePatientsStore()

  const patient = currentPatient ?? patients[0] ?? null

  useEffect(() => {
    if (user?.role === 'patient') {
      void fetchPatients()
    }
  }, [user?.role, fetchPatients])

  useEffect(() => {
    if (patient?.id) {
      void fetchPatientRecords(patient.id)
    }
  }, [patient?.id, fetchPatientRecords])

  const recentRecords = useMemo(
    () => patientRecords.slice(0, 5),
    [patientRecords],
  )

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-bold text-gray-900">
          {patient
            ? patient.fio
            : user
              ? `${user.first_name} ${user.last_name}`
              : 'Личный кабинет'}
        </h1>
        <p className="mt-1 text-gray-500">
          Здесь собраны ваши медицинские записи и история наблюдений.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card title="Карточка пациента">
          <p className="text-3xl font-bold text-primary-600">
            {patient ? '1' : '0'}
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Для пациента доступна собственная карточка и связанные с ней записи.
          </p>
          <div className="mt-4">
            <Link to={patient?.id ? `/patients/${patient.id}` : '/patients'}>
              <Button variant="outline" size="sm" disabled={!patient?.id}>
                Открыть карточку
              </Button>
            </Link>
          </div>
        </Card>

        <Card title="Всего записей">
          <p className="text-3xl font-bold text-primary-600">{patientRecords.length}</p>
          <p className="mt-2 text-sm text-gray-500">
            Все записи immutable. Обсуждение по ним ведётся через комментарии врачей.
          </p>
        </Card>

        <Card title="Последнее событие">
          <p className="text-lg font-semibold text-gray-900">
            {patient?.lastVisit
              ? new Date(patient.lastVisit).toLocaleDateString()
              : 'Пока нет данных'}
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Дата последней медицинской записи в вашей карточке.
          </p>
        </Card>
      </div>

      <Card title="Последние записи">
        {recentRecords.length === 0 ? (
          <p className="py-10 text-center text-gray-500">Записей пока нет.</p>
        ) : (
          <div className="space-y-3">
            {recentRecords.map((record) => (
              <Link
                key={record.id}
                to={patient ? `/patients/${patient.id}` : '/patients'}
                className="block rounded-lg border border-gray-200 px-4 py-4 transition hover:border-primary-200 hover:bg-gray-50"
              >
                <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  <span className="inline-flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    {new Date(record.eventDate).toLocaleDateString()}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <FileText className="h-4 w-4" />
                    {record.recordType}
                  </span>
                  <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs text-primary-700">
                    {record.status}
                  </span>
                </div>
                <h3 className="mt-2 font-semibold text-gray-900">
                  {record.title || 'Медицинская запись'}
                </h3>
                {record.practitioner?.full_name && (
                  <p className="mt-1 inline-flex items-center gap-1 text-sm text-gray-500">
                    <Stethoscope className="h-4 w-4" />
                    {record.practitioner.full_name}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

export default PatientDashboard
