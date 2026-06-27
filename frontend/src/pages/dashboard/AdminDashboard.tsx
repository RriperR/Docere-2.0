import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  Archive,
  CheckCircle,
  Clock3,
  FileText,
  LockKeyhole,
  Share2,
  ShieldCheck,
  Users,
} from 'lucide-react'

import api from '../../api/api'
import { Button } from '../../components/common/Button'

type AuditCategory = 'all' | 'access' | 'changes' | 'auth'

interface AdminSummary {
  users: {
    total: number
    active: number
    blocked: number
    doctors: number
    patients: number
    admins: number
  }
  patient_cards_total: number
  archives: {
    total: number
    processing: number
    needs_review: number
    failed: number
    completed: number
  }
  sharing: {
    pending_requests: number
    active_requests: number
  }
}

interface AuditEvent {
  id: string
  actor_fio: string | null
  actor_email: string | null
  event_type: string
  entity_type: string
  entity_id: string
  metadata_json: Record<string, unknown>
  created_at: string
}

const categoryLabel: Record<AuditCategory, string> = {
  all: 'Все события',
  access: 'Доступ',
  changes: 'Изменения',
  auth: 'Авторизация',
}

const eventLabels: Record<string, string> = {
  login: 'Вход в систему',
  user_status_changed: 'Статус пользователя изменён',
  share_request_created: 'Создан запрос доступа',
  share_request_accepted: 'Доступ принят',
  share_request_declined: 'Запрос доступа отклонён',
  share_request_revoked: 'Доступ отозван',
  medical_record_created: 'Создана медицинская запись',
  medical_record_confirmed: 'Медицинская запись подтверждена',
  import_job_resolved: 'Импорт архива подтверждён',
}

const emptySummary: AdminSummary = {
  users: { total: 0, active: 0, blocked: 0, doctors: 0, patients: 0, admins: 0 },
  patient_cards_total: 0,
  archives: { total: 0, processing: 0, needs_review: 0, failed: 0, completed: 0 },
  sharing: { pending_requests: 0, active_requests: 0 },
}

const getAuditCategory = (eventType: string): Exclude<AuditCategory, 'all'> => {
  const normalized = eventType.toLowerCase()
  if (normalized.includes('login') || normalized.includes('auth') || normalized.includes('token')) {
    return 'auth'
  }
  if (
    normalized.includes('share') ||
    normalized.includes('access') ||
    normalized.includes('view') ||
    normalized.includes('download')
  ) {
    return 'access'
  }
  return 'changes'
}

const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))

const formatMetadata = (metadata: Record<string, unknown>) => {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined)
  if (entries.length === 0) return 'Без дополнительных данных'
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(', ')
}

const AdminDashboard: React.FC = () => {
  const [summary, setSummary] = useState<AdminSummary>(emptySummary)
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [activeCategory, setActiveCategory] = useState<AuditCategory>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadDashboard = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [summaryResponse, auditResponse] = await Promise.all([
          api.get<AdminSummary>('/admin/summary'),
          api.get<AuditEvent[]>('/admin/audit-events', { params: { limit: 20 } }),
        ])
        setSummary(summaryResponse.data)
        setAuditEvents(auditResponse.data)
      } catch {
        setError('Не удалось загрузить административную сводку')
      } finally {
        setIsLoading(false)
      }
    }

    void loadDashboard()
  }, [])

  const filteredEvents = useMemo(
    () =>
      activeCategory === 'all'
        ? auditEvents
        : auditEvents.filter((event) => getAuditCategory(event.event_type) === activeCategory),
    [activeCategory, auditEvents],
  )

  const stats = [
    {
      label: 'Всего пользователей',
      value: summary.users.total,
      detail: `${summary.users.active} активных`,
      icon: <Users className="h-5 w-5 text-primary-600" />,
      color: 'bg-primary-50',
    },
    {
      label: 'Врачи',
      value: summary.users.doctors,
      detail: `${summary.users.patients} пациентов`,
      icon: <ShieldCheck className="h-5 w-5 text-accent-600" />,
      color: 'bg-accent-50',
    },
    {
      label: 'Карточки пациентов',
      value: summary.patient_cards_total,
      detail: `${summary.users.blocked} заблокировано`,
      icon: <Activity className="h-5 w-5 text-secondary-600" />,
      color: 'bg-secondary-50',
    },
    {
      label: 'Активные доступы',
      value: summary.sharing.active_requests,
      detail: `${summary.sharing.pending_requests} ожидают ответа`,
      icon: <Share2 className="h-5 w-5 text-success-600" />,
      color: 'bg-success-50',
    },
  ]

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Панель администратора</h1>
          <p className="mt-0.5 text-sm text-gray-500">Оперативная сводка системы</p>
        </div>
        <Link to="/admin">
          <Button variant="outline" size="sm" icon={<Users className="h-4 w-4" />}>
            Управление пользователями
          </Button>
        </Link>
      </motion.div>

      {error && (
        <div className="rounded-lg border border-error-200 bg-error-50 p-4 text-sm text-error-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.35 }}
            className="rounded-lg border border-gray-200 bg-white p-5"
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${stat.color}`}>{stat.icon}</div>
            <p className="mt-3 text-3xl font-bold text-gray-900">{isLoading ? '—' : stat.value}</p>
            <p className="text-sm font-medium text-gray-700">{stat.label}</p>
            <p className="mt-1 text-xs text-gray-500">{isLoading ? 'Загрузка...' : stat.detail}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
            <div className="flex items-center gap-2">
              <Archive className="h-5 w-5 text-primary-600" />
              <h2 className="font-semibold text-gray-900">Архивы</h2>
            </div>
            <Link to="/upload" className="text-sm font-medium text-primary-600 hover:text-primary-700">
              Открыть
            </Link>
          </div>
          <div className="divide-y divide-gray-100 px-5">
            <MetricRow icon={<Clock3 className="h-4 w-4 text-primary-500" />} label="В обработке" value={summary.archives.processing} loading={isLoading} />
            <MetricRow icon={<AlertTriangle className="h-4 w-4 text-warning-500" />} label="Требуют review" value={summary.archives.needs_review} loading={isLoading} />
            <MetricRow icon={<AlertTriangle className="h-4 w-4 text-error-500" />} label="Завершились с ошибкой" value={summary.archives.failed} loading={isLoading} />
            <MetricRow icon={<CheckCircle className="h-4 w-4 text-success-500" />} label="Успешно завершены" value={summary.archives.completed} loading={isLoading} />
          </div>
        </section>

        <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
            <div className="flex items-center gap-2">
              <Share2 className="h-5 w-5 text-primary-600" />
              <h2 className="font-semibold text-gray-900">Доступы к записям</h2>
            </div>
            <Link to="/share-requests" className="text-sm font-medium text-primary-600 hover:text-primary-700">
              Открыть
            </Link>
          </div>
          <div className="divide-y divide-gray-100 px-5">
            <MetricRow icon={<Clock3 className="h-4 w-4 text-warning-500" />} label="Ожидают ответа" value={summary.sharing.pending_requests} loading={isLoading} />
            <MetricRow icon={<Share2 className="h-4 w-4 text-success-500" />} label="Активные запросы" value={summary.sharing.active_requests} loading={isLoading} />
            <MetricRow icon={<LockKeyhole className="h-4 w-4 text-gray-500" />} label="Заблокированные аккаунты" value={summary.users.blocked} loading={isLoading} />
            <MetricRow icon={<ShieldCheck className="h-4 w-4 text-primary-500" />} label="Администраторы" value={summary.users.admins} loading={isLoading} />
          </div>
        </section>
      </div>

      <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-gray-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Последние события</h2>
          </div>
          <div className="flex gap-1 overflow-x-auto" role="group" aria-label="Фильтр событий">
            {(Object.keys(categoryLabel) as AuditCategory[]).map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => setActiveCategory(category)}
                className={`whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  activeCategory === category
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {categoryLabel[category]}
              </button>
            ))}
          </div>
        </div>

        {!isLoading && filteredEvents.length === 0 && (
          <div className="p-6 text-center text-sm text-gray-500">Событий в этой категории пока нет</div>
        )}

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr className="border-b border-gray-100 text-left">
                {['Событие', 'Инициатор', 'Объект', 'Время', 'Детали'].map((heading) => (
                  <th key={heading} className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredEvents.map((event) => {
                const category = getAuditCategory(event.event_type)
                return (
                  <tr key={event.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900">
                      <span className="flex items-center gap-2">
                        {category === 'auth' ? (
                          <LockKeyhole className="h-4 w-4 shrink-0 text-primary-500" />
                        ) : category === 'access' ? (
                          <Share2 className="h-4 w-4 shrink-0 text-success-500" />
                        ) : (
                          <Activity className="h-4 w-4 shrink-0 text-warning-500" />
                        )}
                        {eventLabels[event.event_type] ?? event.event_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-600">
                      <span className="block">{event.actor_fio ?? 'Система'}</span>
                      {event.actor_email && <span className="block text-xs text-gray-400">{event.actor_email}</span>}
                    </td>
                    <td className="px-5 py-3 text-gray-600">
                      {event.entity_type} · {event.entity_id.slice(0, 8)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-gray-500">{formatDateTime(event.created_at)}</td>
                    <td className="max-w-xs truncate px-5 py-3 text-gray-500" title={formatMetadata(event.metadata_json)}>
                      {formatMetadata(event.metadata_json)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function MetricRow({
  icon,
  label,
  value,
  loading,
}: {
  icon: React.ReactNode
  label: string
  value: number
  loading: boolean
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm text-gray-700">{label}</span>
      </div>
      <span className="min-w-8 text-right text-sm font-semibold text-gray-900">{loading ? '—' : value}</span>
    </div>
  )
}

export default AdminDashboard
