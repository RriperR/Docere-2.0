import React, { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Calendar, FileText, Users } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

const DoctorDashboard: React.FC = () => {
  const { user } = useAuthStore()
  const { patients, fetchPatients } = usePatientsStore()

  useEffect(() => {
    void fetchPatients()
  }, [fetchPatients])

  const totalRecords = useMemo(
    () => patients.reduce((acc, patient) => acc + patient.recordCount, 0),
    [patients],
  )

  const recentPatients = useMemo(
    () =>
      [...patients]
        .sort((a, b) => {
          const left = a.lastVisit ? new Date(a.lastVisit).getTime() : 0
          const right = b.lastVisit ? new Date(b.lastVisit).getTime() : 0
          return right - left
        })
        .slice(0, 5),
    [patients],
  )

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-bold text-gray-900">
          {user ? `${user.first_name} ${user.last_name}` : 'Кабинет врача'}
        </h1>
        <p className="mt-1 text-gray-500">
          Рабочий обзор по доступным карточкам пациентов и медицинским записям.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card title="Пациентов в работе">
          <p className="text-3xl font-bold text-primary-600">{patients.length}</p>
          <p className="mt-2 text-sm text-gray-500">
            Доступные вам карточки пациентов с подтверждёнными связями и записями.
          </p>
        </Card>

        <Card title="Всего записей">
          <p className="text-3xl font-bold text-primary-600">{totalRecords}</p>
          <p className="mt-2 text-sm text-gray-500">
            Суммарное число доступных медицинских записей по вашим пациентам.
          </p>
        </Card>

        <Card title="Быстрый переход">
          <p className="text-sm text-gray-500">
            Основной рабочий сценарий проходит через карточки пациентов и детали записей.
          </p>
          <div className="mt-4">
            <Link to="/patients">
              <Button variant="outline" size="sm">
                Открыть список пациентов
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      <Card title="Недавно обновлённые карточки">
        {recentPatients.length === 0 ? (
          <p className="py-10 text-center text-gray-500">Пока нет доступных карточек.</p>
        ) : (
          <div className="space-y-3">
            {recentPatients.map((patient) => (
              <Link
                key={patient.id}
                to={`/patients/${patient.id}`}
                className="flex flex-col gap-2 rounded-lg border border-gray-200 px-4 py-4 transition hover:border-primary-200 hover:bg-gray-50 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <h3 className="font-semibold text-gray-900">{patient.fio}</h3>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-gray-500">
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {patient.status}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <FileText className="h-4 w-4" />
                      {patient.recordCount}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {patient.lastVisit
                        ? new Date(patient.lastVisit).toLocaleDateString()
                        : 'Без записей'}
                    </span>
                  </div>
                </div>
                <span className="text-sm font-medium text-primary-600">Открыть карточку</span>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

export default DoctorDashboard
