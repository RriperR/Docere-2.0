import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Database,
  HardDrive,
  ShieldCheck,
  TrendingUp,
  Users,
  XCircle,
} from 'lucide-react'

import { Button } from '../../components/common/Button'
import { usePatientsStore } from '../../stores/patientsStore'

type AuditCategory = 'all' | 'access' | 'changes' | 'auth'

const categoryLabel: Record<AuditCategory, string> = {
  all: 'Все события',
  access: 'Доступ',
  changes: 'Изменения',
  auth: 'Авторизация',
}

const auditLogs = [
  { id: 'log1', action: 'Изменение роли пользователя', user: 'Мария Иванова', targetUser: 'Иван Смирнов', timestamp: '2024-03-15 14:30:22', details: 'patient → doctor', category: 'changes', severity: 'warning' },
  { id: 'log2', action: 'Просмотр медицинской карты', user: 'Д-р Алексей Козлов', targetUser: 'Елена Вильямс', timestamp: '2024-03-15 13:45:11', details: 'Просмотр истории болезни', category: 'access', severity: 'info' },
  { id: 'log3', action: 'Новый пациент зарегистрирован', user: 'Система', targetUser: 'Михаил Браун', timestamp: '2024-03-15 10:12:05', details: 'Самостоятельная регистрация', category: 'changes', severity: 'info' },
  { id: 'log4', action: 'Запись изменена', user: 'Д-р Мария Иванова', targetUser: 'Иван Doe', timestamp: '2024-03-14 16:22:45', details: 'Обновление диагноза', category: 'changes', severity: 'info' },
  { id: 'log5', action: 'Неудачный вход в систему', user: 'Неизвестно', targetUser: 'N/A', timestamp: '2024-03-14 08:17:33', details: 'Множественные неудачные попытки', category: 'auth', severity: 'error' },
]

const userStats = { total: 145, doctors: 32, patients: 110, admins: 3 }
const roleRequests = { pending: 8, approved: 24, rejected: 5 }

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    Online: 'text-success-700 bg-success-50',
    Operational: 'text-success-700 bg-success-50',
    'No backlog': 'text-success-700 bg-success-50',
    'Degraded': 'text-warning-700 bg-warning-50',
    'Error': 'text-error-700 bg-error-50',
  }
  return (
    <span className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? 'text-gray-700 bg-gray-100'}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  )
}

const AdminDashboard: React.FC = () => {
  const { patients, fetchPatients } = usePatientsStore()
  const [activeCategory, setActiveCategory] = useState<AuditCategory>('all')

  useEffect(() => {
    fetchPatients()
  }, [fetchPatients])

  const filteredLogs = activeCategory === 'all'
    ? auditLogs
    : auditLogs.filter((l) => l.category === activeCategory)

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
            Панель администратора
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Управление пользователями, мониторинг и аудит системы.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/admin">
            <Button variant="outline" size="sm">Управление системой</Button>
          </Link>
        </div>
      </motion.div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Всего пользователей', value: userStats.total, icon: <Users className="h-5 w-5 text-primary-600" />, color: 'bg-primary-50', trend: '+3 за неделю' },
          { label: 'Врачей', value: userStats.doctors, icon: <ShieldCheck className="h-5 w-5 text-accent-600" />, color: 'bg-accent-50', trend: undefined },
          { label: 'Пациентов', value: userStats.patients, icon: <Activity className="h-5 w-5 text-secondary-600" />, color: 'bg-secondary-50', trend: '+12 за неделю' },
          { label: 'Карточек пациентов', value: patients.length, icon: <TrendingUp className="h-5 w-5 text-success-600" />, color: 'bg-success-50', trend: undefined },
        ].map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.4 }}
            className="rounded-xl border border-gray-100 bg-white p-5 shadow-card"
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${card.color}`}>
              {card.icon}
            </div>
            <p className="mt-3 text-3xl font-bold text-gray-900">{card.value}</p>
            <p className="text-sm text-gray-600">{card.label}</p>
            {card.trend && (
              <p className="mt-1 flex items-center gap-1 text-xs text-success-600">
                <TrendingUp className="h-3 w-3" />
                {card.trend}
              </p>
            )}
          </motion.div>
        ))}
      </div>

      {/* Role requests + System status */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.4 }}
          className="rounded-xl border border-gray-100 bg-white shadow-card"
        >
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary-500" />
              <h2 className="font-semibold text-gray-900">Заявки на роль врача</h2>
            </div>
            {roleRequests.pending > 0 && (
              <span className="rounded-full bg-warning-100 px-2.5 py-0.5 text-xs font-bold text-warning-700">
                {roleRequests.pending} ожидают
              </span>
            )}
          </div>
          <div className="p-6">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="rounded-xl bg-warning-50 p-4">
                <p className="text-2xl font-bold text-warning-600">{roleRequests.pending}</p>
                <p className="mt-1 text-xs text-gray-500">Ожидают</p>
              </div>
              <div className="rounded-xl bg-success-50 p-4">
                <p className="text-2xl font-bold text-success-600">{roleRequests.approved}</p>
                <p className="mt-1 text-xs text-gray-500">Одобрено</p>
              </div>
              <div className="rounded-xl bg-error-50 p-4">
                <p className="text-2xl font-bold text-error-600">{roleRequests.rejected}</p>
                <p className="mt-1 text-xs text-gray-500">Отклонено</p>
              </div>
            </div>
            <Link to="/admin" className="mt-4 block">
              <Button fullWidth variant="outline" size="sm">
                Рассмотреть заявки
              </Button>
            </Link>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="rounded-xl border border-gray-100 bg-white shadow-card"
        >
          <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
            <Database className="h-5 w-5 text-primary-500" />
            <h2 className="font-semibold text-gray-900">Статус системы</h2>
          </div>
          <div className="divide-y divide-gray-50 px-6">
            {[
              { label: 'База данных', value: 'Online', icon: <Database className="h-4 w-4 text-gray-400" /> },
              { label: 'Хранилище файлов', value: 'Online', icon: <HardDrive className="h-4 w-4 text-gray-400" /> },
              { label: 'Очередь задач', value: 'No backlog', icon: <Activity className="h-4 w-4 text-gray-400" /> },
              { label: 'API сервисы', value: 'Operational', icon: <CheckCircle className="h-4 w-4 text-gray-400" /> },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-2">
                  {item.icon}
                  <span className="text-sm text-gray-700">{item.label}</span>
                </div>
                <StatusBadge status={item.value} />
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Audit log */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        className="rounded-xl border border-gray-100 bg-white shadow-card"
      >
        <div className="flex flex-col gap-3 border-b border-gray-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-primary-500" />
            <h2 className="font-semibold text-gray-900">Журнал аудита</h2>
          </div>
          <div className="flex gap-1 overflow-x-auto">
            {(Object.keys(categoryLabel) as AuditCategory[]).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  activeCategory === cat
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {categoryLabel[cat]}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left">
                {['Событие', 'Пользователь', 'Целевой объект', 'Время', 'Детали'].map((h) => (
                  <th key={h} className="px-6 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-2">
                      {log.severity === 'error' ? (
                        <XCircle className="h-4 w-4 shrink-0 text-error-500" />
                      ) : log.severity === 'warning' ? (
                        <AlertTriangle className="h-4 w-4 shrink-0 text-warning-500" />
                      ) : (
                        <CheckCircle className="h-4 w-4 shrink-0 text-success-500" />
                      )}
                      <span className="font-medium text-gray-900">{log.action}</span>
                    </div>
                  </td>
                  <td className="px-6 py-3 text-gray-600">{log.user}</td>
                  <td className="px-6 py-3 text-gray-600">{log.targetUser}</td>
                  <td className="px-6 py-3 text-gray-400">{log.timestamp}</td>
                  <td className="px-6 py-3 text-gray-500">{log.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  )
}

export default AdminDashboard
