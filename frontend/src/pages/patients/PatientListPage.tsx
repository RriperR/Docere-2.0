import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Calendar, FileText, Grid3X3, LayoutList, Plus, Search, X } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '../../components/common/Button'
import { DateInput } from '../../components/common/DateInput'
import { Input } from '../../components/common/Input'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

type ViewMode = 'table' | 'grid'

type ApiError = {
  response?: { data?: { detail?: string } }
}

const buildFio = (lastName: string, firstName: string, middleName: string): string =>
  [lastName, firstName, middleName]
    .map((p) => p.trim())
    .filter(Boolean)
    .join(' ')

const accessContextLabel = (ctx: string): string =>
  ctx === 'shared' ? 'Sharing' : ctx === 'created' ? 'Локальная' : 'Моя'

const accessContextClasses = (ctx: string): string =>
  ctx === 'shared'
    ? 'bg-warning-50 text-warning-700 border-warning-200'
    : ctx === 'created'
      ? 'bg-accent-50 text-accent-700 border-accent-200'
      : 'bg-success-50 text-success-700 border-success-200'

const avatarColors = [
  'bg-primary-500', 'bg-accent-500', 'bg-secondary-500',
  'bg-success-500', 'bg-warning-500', 'bg-error-400',
]

function getInitials(fio: string): string {
  const parts = fio.trim().split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return fio[0]?.toUpperCase() ?? '?'
}

function getColor(fio: string): string {
  const sum = Array.from(fio).reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return avatarColors[sum % avatarColors.length]
}

function EmptyState({ onAdd, canCreate }: { onAdd: () => void; canCreate: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100">
        <FileText className="h-7 w-7 text-gray-400" />
      </div>
      <p className="mt-4 text-base font-semibold text-gray-900">Пациентов пока нет</p>
      <p className="mt-1 text-sm text-gray-500">Карточки пациентов появятся здесь после создания</p>
      {canCreate && (
        <button
          onClick={onAdd}
          className="mt-4 flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          <Plus className="h-4 w-4" />
          Добавить первого пациента
        </button>
      )}
    </div>
  )
}

const PatientListPage: React.FC = () => {
  const { user } = useAuthStore()
  const { filteredPatients, fetchPatients, createPatient, searchPatients, filterPatientsByDate, isLoading, error } =
    usePatientsStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [isModalOpen, setModalOpen] = useState(false)
  const [isSubmitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [form, setForm] = useState({ lastName: '', firstName: '', middleName: '', email: '', phone: '', birthday: '' })

  useEffect(() => { void fetchPatients() }, [fetchPatients])
  useEffect(() => { searchPatients(searchQuery) }, [searchQuery, searchPatients])
  useEffect(() => { filterPatientsByDate(startDate, endDate) }, [startDate, endDate, filterPatientsByDate])

  const canCreatePatient = user?.role === 'doctor' || user?.role === 'admin'

  const closeModal = () => {
    setModalOpen(false)
    setFormError(null)
    setForm({ lastName: '', firstName: '', middleName: '', email: '', phone: '', birthday: '' })
  }

  const handleCreatePatient = async () => {
    setFormError(null)
    setSubmitting(true)
    try {
      await createPatient({
        fio: buildFio(form.lastName, form.firstName, form.middleName),
        email: form.email || undefined,
        phone: form.phone || undefined,
        date_of_birth: form.birthday || undefined,
      })
      closeModal()
    } catch (err: unknown) {
      const apiError = err as ApiError
      setFormError(apiError.response?.data?.detail || 'Не удалось создать карточку пациента')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Карточки пациентов</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {user?.role === 'patient'
              ? 'Ваши доступные карточки и медицинские записи.'
              : 'Пациенты, к которым у вас есть доступ.'}
          </p>
        </div>
        {canCreatePatient && (
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setModalOpen(true)} size="sm">
            Добавить пациента
          </Button>
        )}
      </motion.div>

      {/* Filters */}
      <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <Input
              placeholder="Поиск по ФИО, email или телефону"
              icon={<Search className="h-4 w-4" />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <DateInput
              icon={<Calendar className="h-4 w-4" />}
              value={startDate}
              onChange={(value) => setStartDate(value ?? '')}
              fullWidth={false}
              className="w-36"
            />
            <DateInput
              icon={<Calendar className="h-4 w-4" />}
              value={endDate}
              onChange={(value) => setEndDate(value ?? '')}
              fullWidth={false}
              className="w-36"
            />
            <div className="flex items-start rounded-lg border border-gray-200 overflow-hidden">
              <button
                onClick={() => setViewMode('table')}
                className={`p-2 transition-colors ${viewMode === 'table' ? 'bg-primary-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                title="Табличный вид"
              >
                <LayoutList className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 transition-colors ${viewMode === 'grid' ? 'bg-primary-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                title="Карточный вид"
              >
                <Grid3X3 className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="rounded-xl border border-gray-100 bg-white shadow-card">
        {isLoading ? (
          <div className="space-y-3 p-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-4 animate-pulse">
                <div className="h-10 w-10 rounded-full bg-gray-200" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-48 rounded bg-gray-200" />
                  <div className="h-3 w-32 rounded bg-gray-200" />
                </div>
                <div className="h-3 w-24 rounded bg-gray-200" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-error-600">{error}</p>
          </div>
        ) : filteredPatients.length === 0 ? (
          <EmptyState onAdd={() => setModalOpen(true)} canCreate={canCreatePatient} />
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredPatients.map((patient) => (
              <Link
                key={patient.id}
                to={`/patients/${patient.id}`}
                className="group flex flex-col rounded-xl border border-gray-100 p-4 transition-all hover:border-primary-200 hover:shadow-card-hover"
              >
                <div className="flex items-start justify-between">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl text-sm font-bold text-white ${getColor(patient.fio)}`}>
                    {getInitials(patient.fio)}
                  </div>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${accessContextClasses(patient.accessContext)}`}>
                    {accessContextLabel(patient.accessContext)}
                  </span>
                </div>
                <p className="mt-3 font-semibold text-gray-900 group-hover:text-primary-700 truncate">
                  {patient.fio}
                </p>
                <p className="text-xs text-gray-500 truncate">{patient.email || '—'}</p>
                <div className="mt-3 flex items-center justify-between border-t border-gray-50 pt-3 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <FileText className="h-3.5 w-3.5" />
                    {patient.recordCount} записей
                  </span>
                  {patient.lastVisit && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      {format(new Date(patient.lastVisit), 'dd.MM.yy')}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  {['Пациент', 'Дата рождения', 'Последняя запись', 'Доступ', 'Записей', ''].map((h) => (
                    <th key={h} className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-400">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredPatients.map((patient) => (
                  <tr key={patient.id} className="group hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white ${getColor(patient.fio)}`}>
                          {getInitials(patient.fio)}
                        </div>
                        <div>
                          <p className="font-semibold text-gray-900 group-hover:text-primary-700">{patient.fio}</p>
                          <p className="text-xs text-gray-500">{patient.email || '—'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {patient.birthday ? format(new Date(patient.birthday), 'dd.MM.yyyy') : '—'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {patient.lastVisit ? format(new Date(patient.lastVisit), 'dd.MM.yyyy') : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${accessContextClasses(patient.accessContext)}`}>
                        {accessContextLabel(patient.accessContext)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-gray-400" />
                        {patient.recordCount}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        to={`/patients/${patient.id}`}
                        className="text-sm font-medium text-primary-600 hover:text-primary-700"
                      >
                        Открыть →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Patient Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/60 p-4 backdrop-blur-sm"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
            >
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900">Новый пациент</h2>
                <button onClick={closeModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100">
                  <X className="h-5 w-5" />
                </button>
              </div>
              {formError && (
                <div className="mb-4 rounded-lg bg-error-50 px-3 py-2 text-sm text-error-700">
                  {formError}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <Input label="Фамилия *" value={form.lastName} onChange={(e) => setForm({ ...form, lastName: e.target.value })} />
                <Input label="Имя *" value={form.firstName} onChange={(e) => setForm({ ...form, firstName: e.target.value })} />
                <Input label="Отчество" className="col-span-2" value={form.middleName} onChange={(e) => setForm({ ...form, middleName: e.target.value })} />
                <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                <Input label="Телефон" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                <DateInput label="Дата рождения" className="col-span-2" value={form.birthday} onChange={(value) => setForm({ ...form, birthday: value ?? '' })} />
              </div>
              <div className="mt-5 flex justify-end gap-2">
                <Button variant="outline" onClick={closeModal}>Отмена</Button>
                <Button onClick={handleCreatePatient} isLoading={isSubmitting} disabled={!form.firstName.trim() || !form.lastName.trim()}>
                  Создать
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default PatientListPage
