import React, { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowUpRight,
  Calendar,
  ChevronRight,
  FileText,
  TrendingUp,
  Users,
} from 'lucide-react'

import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { format } from 'date-fns'

function KpiCard({
  title,
  value,
  description,
  icon,
  color,
  trend,
  delay = 0,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ReactNode
  color: string
  trend?: string
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="rounded-xl border border-gray-100 bg-white p-5 shadow-card"
    >
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
          {icon}
        </div>
        {trend && (
          <span className="flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-xs font-medium text-success-700">
            <TrendingUp className="h-3 w-3" />
            {trend}
          </span>
        )}
      </div>
      <p className="mt-4 text-3xl font-bold text-gray-900">{value}</p>
      <p className="text-sm font-medium text-gray-700">{title}</p>
      <p className="mt-1 text-xs text-gray-400">{description}</p>
    </motion.div>
  )
}

function getInitials(fio: string): string {
  const parts = fio.trim().split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return fio[0]?.toUpperCase() ?? '?'
}

const avatarColors = [
  'bg-primary-500', 'bg-accent-500', 'bg-secondary-500', 'bg-success-500', 'bg-warning-500',
]

const DoctorDashboard: React.FC = () => {
  const { user } = useAuthStore()
  const { patients, fetchPatients } = usePatientsStore()

  useEffect(() => {
    void fetchPatients()
  }, [fetchPatients])

  const totalRecords = useMemo(
    () => patients.reduce((acc, p) => acc + p.recordCount, 0),
    [patients],
  )

  const recentPatients = useMemo(
    () =>
      [...patients]
        .sort((a, b) => {
          const l = a.lastVisit ? new Date(a.lastVisit).getTime() : 0
          const r = b.lastVisit ? new Date(b.lastVisit).getTime() : 0
          return r - l
        })
        .slice(0, 6),
    [patients],
  )

  const today = new Date().toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Добро пожаловать,{' '}
            {user ? `${user.first_name} ${user.last_name}` : 'Доктор'}
          </h1>
          <p className="mt-0.5 text-sm capitalize text-gray-500">{today}</p>
        </div>
        <Link to="/patients">
          <Button icon={<Users className="h-4 w-4" />} size="sm">
            Все пациенты
          </Button>
        </Link>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          title="Пациентов в работе"
          value={patients.length}
          description="Доступные карточки пациентов"
          icon={<Users className="h-5 w-5 text-primary-600" />}
          color="bg-primary-50"
          delay={0.05}
        />
        <KpiCard
          title="Всего записей"
          value={totalRecords}
          description="Суммарно по всем пациентам"
          icon={<FileText className="h-5 w-5 text-accent-600" />}
          color="bg-accent-50"
          delay={0.1}
        />
        <KpiCard
          title="Среднее записей"
          value={patients.length > 0 ? (totalRecords / patients.length).toFixed(1) : '—'}
          description="Записей на одного пациента"
          icon={<TrendingUp className="h-5 w-5 text-secondary-600" />}
          color="bg-secondary-50"
          delay={0.15}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white shadow-card"
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Последние активные карточки</h2>
          <Link to="/patients" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
            Все пациенты
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>

        {recentPatients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <Users className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-gray-900">Пациентов пока нет</p>
            <p className="mt-1 text-xs text-gray-500">Карточки появятся после первой записи</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {recentPatients.map((patient, i) => (
              <Link
                key={patient.id}
                to={`/patients/${patient.id}`}
                className="group flex items-center gap-4 px-6 py-4 transition-colors hover:bg-gray-50"
              >
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white ${avatarColors[i % avatarColors.length]}`}>
                  {getInitials(patient.fio)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-gray-900 group-hover:text-primary-700">
                    {patient.fio}
                  </p>
                  <div className="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <FileText className="h-3.5 w-3.5" />
                      {patient.recordCount} записей
                    </span>
                    {patient.lastVisit && (
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {format(new Date(patient.lastVisit), 'dd.MM.yyyy')}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-400 transition-colors" />
              </Link>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  )
}

export default DoctorDashboard
