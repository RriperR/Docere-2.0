import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowUpRight,
  Calendar,
  ChevronRight,
  Clock,
  FileText,
  Inbox,
  Share2,
  UploadCloud,
  Plus,
  ArrowRight,
  Users,
} from 'lucide-react'

import Attention from '../cases/Attention'
import RecentCases from './RecentCases'
import { secondaryButtonClass } from '../cases/styles'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useShareRequestsStore } from '../../stores/shareRequestsStore'
import { useUploadStore } from '../../stores/uploadStore'
import { format } from 'date-fns'

function KpiCard({
  title,
  value,
  description,
  icon,
  color,
  delay = 0,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ReactNode
  color: string
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="rounded-xl border border-gray-100 bg-white p-5 shadow-card"
    >
      <div className="flex items-center justify-between gap-4">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
          {icon}
        </div>
        <p className="text-3xl font-bold text-gray-900">{value}</p>
      </div>
      <p className="mt-3 text-sm font-medium text-gray-700">{title}</p>
      <p className="mt-1 text-xs text-gray-500">{description}</p>
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
  const { patients, fetchPatients, error: patientsError } = usePatientsStore()
  const { jobs, listJobs, error: importsError } = useUploadStore()
  const { inbox, fetchInbox, error: sharesError } = useShareRequestsStore()

  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void Promise.all([fetchPatients(), listJobs(), fetchInbox()]).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [fetchPatients, listJobs, fetchInbox, revision])

  const startingWork = !loading && !patientsError && !patients.some(patient => patient.accessContext !== 'own_confirmed')

  const totalRecords = useMemo(
    () => patients.reduce((acc, p) => acc + p.recordCount, 0),
    [patients],
  )

  const reviewTasks = useMemo(() => {
    const importTasks = jobs
      .filter((job) => ['needs_review', 'failed', 'completed_with_warnings'].includes(job.status))
      .slice(0, 5)
      .map((job) => ({
        id: `import-${job.id}`,
        title: job.status === 'needs_review' ? 'Проверить импорт архива' : job.status === 'failed' ? 'Разобрать ошибку импорта' : 'Импорт с предупреждениями',
        description: job.original_filename ?? 'archive.zip',
        meta: new Date(job.created_at).toLocaleString('ru-RU'),
        timestamp: new Date(job.created_at).getTime(),
        to: job.status === 'needs_review' ? `/upload/review/${job.id}` : `/upload/status/${job.id}`,
        icon: <Inbox className="h-4 w-4" />,
        tone: job.status === 'failed' ? 'text-error-700 bg-error-50' : 'text-warning-700 bg-warning-50',
      }))

    const shareTasks = inbox
      .filter((request) => request.status === 'pending' && (!request.expires_at || new Date(request.expires_at).getTime() > Date.now()))
      .slice(0, 5)
      .map((request) => ({
        id: `share-${request.id}`,
        title: 'Приглашение к записям',
        description: `${request.from_user.fio} · ${request.shares.length} записей`,
        meta: new Date(request.created_at).toLocaleString('ru-RU'),
        timestamp: new Date(request.created_at).getTime(),
        to: '/share-requests',
        icon: <Share2 className="h-4 w-4" />,
        tone: 'text-primary-700 bg-primary-50',
      }))

    return [...importTasks, ...shareTasks]
      .sort((left, right) => right.timestamp - left.timestamp)
      .slice(0, 6)
  }, [inbox, jobs])

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
      <section className="relative overflow-hidden rounded-3xl bg-primary-950 p-6 text-white sm:p-8">
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-32 h-96 w-96 rounded-full border-[50px] border-secondary-400/10" />
        <div className="relative flex flex-wrap items-center justify-between gap-3 text-xs font-medium text-primary-200">
          <span className="uppercase tracking-[0.18em]">Рабочее пространство врача</span><span className="capitalize">{today}</span>
        </div>
        <div className="relative mt-6 max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Здравствуйте, {user?.first_name || 'доктор'}.</h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-primary-100 sm:text-base">{startingWork ? `Начните с пациента: добавьте его карточку или импортируйте документы.${patients.some(patient => patient.accessContext === 'own_confirmed') ? ' Ваша собственная карточка остаётся доступной ниже.' : ''}` : 'Соберите клинический контекст, обсудите его с коллегами и сохраните итог в истории пациента.'}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to={startingWork ? "/patients?create=1" : "/cases/new"} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-primary-950 shadow-xs hover:bg-primary-50">
              <Plus size={18} aria-hidden="true" />{startingWork ? 'Добавить пациента' : 'Новый клинический случай'}</Link>
            <Link to="/upload" className="inline-flex items-center gap-2 rounded-xl border border-white/25 px-4 py-3 text-sm font-medium text-white hover:bg-white/10">
              <UploadCloud size={18} aria-hidden="true" />{startingWork ? 'Импорт документов' : 'Импортировать материалы'}</Link>
          </div>
        </div>
      </section>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <RecentCases />
        <Attention />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard
          title="Доступных пациентов"
          value={loading || patientsError ? '—' : patients.length}
          description="Доступные карточки пациентов"
          icon={<Users className="h-5 w-5 text-primary-600" />}
          color="bg-primary-50"
          delay={0.05}
        />
        <KpiCard
          title="Всего записей"
          value={loading || patientsError ? '—' : totalRecords}
          description="Доступные вам медицинские записи"
          icon={<FileText className="h-5 w-5 text-accent-600" />}
          color="bg-accent-50"
          delay={0.1}
        />
        <KpiCard
          title="Архивов на проверке"
          value={loading || importsError ? '—' : jobs.filter(job => job.status === 'needs_review').length}
          description="Ожидают вашего решения перед импортом"
          icon={<Inbox className="h-5 w-5 text-secondary-600" />}
          color="bg-secondary-50"
          delay={0.15}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18, duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white shadow-card"
      >
        <div className="flex flex-col gap-3 border-b border-gray-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">Рабочая очередь</h2>
            <p className="mt-0.5 text-xs text-gray-500">Импорты, входящие доступы и действия, которые требуют внимания</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-warning-50 px-2.5 py-1 font-medium text-warning-700">
              Архивы: {loading || importsError ? '—' : jobs.filter((job) => job.status === 'needs_review').length}
            </span>
            <span className="rounded-full bg-primary-50 px-2.5 py-1 font-medium text-primary-700">
              Доступы: {loading || sharesError ? '—' : inbox.filter((request) => request.status === 'pending' && (!request.expires_at || new Date(request.expires_at).getTime() > Date.now())).length}
            </span>
          </div>
        </div>

        {loading ? <p role="status" className="p-6 text-sm text-gray-500">Загружаем рабочую очередь…</p> : importsError || sharesError ?
          <p role="alert" className="p-6 text-sm text-error-700">Не удалось загрузить всю очередь. <button className="underline" onClick={() => setRevision(value => value + 1)}>Повторить</button></p> : reviewTasks.length === 0 ? (
          <div className="flex items-center gap-3 px-6 py-5">
            <Clock className="h-5 w-5 shrink-0 text-secondary-600" aria-hidden="true" />
            <p className="text-sm text-gray-500">Все входящие разобраны. Новых импортов и приглашений к записям нет.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {reviewTasks.map((task) => (
              <Link
                key={task.id}
                to={task.to}
                className="group flex items-center gap-4 px-6 py-4 transition-colors hover:bg-gray-50"
              >
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${task.tone}`}>
                  {task.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-gray-900 group-hover:text-primary-700">
                    {task.title}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-gray-500">{task.description}</p>
                </div>
                <div className="hidden text-xs text-gray-500 sm:block">{task.meta}</div>
                <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-primary-400 transition-colors" />
              </Link>
            ))}
          </div>
        )}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white shadow-card"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Последние активные карточки</h2>
          <Link to="/patients" className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
            Все пациенты
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>

        {loading ? <p role="status" className="p-6 text-sm text-gray-500">Загружаем пациентов…</p> : patientsError ?
          <p role="alert" className="p-6 text-sm text-error-700">{patientsError} <button className="underline" onClick={() => setRevision(value => value + 1)}>Повторить</button></p> : recentPatients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <Users className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-gray-900">Пациентов пока нет</p>
            <p className="mt-1 text-xs text-gray-500">Добавьте пациента, чтобы вести историю и начать совместный разбор</p>
            <Link className={`${secondaryButtonClass} mt-4`} to="/patients?create=1">Добавить пациента <ArrowRight size={16} /></Link>
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
                      Записей: {patient.recordCount}
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
