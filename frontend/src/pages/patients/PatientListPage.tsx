import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Calendar, FileText, Plus, Search } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { Input } from '../../components/common/Input'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
}

const buildFio = (lastName: string, firstName: string, middleName: string): string =>
  [lastName, firstName, middleName]
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .join(' ')

const PatientListPage: React.FC = () => {
  const { user } = useAuthStore()
  const {
    filteredPatients,
    fetchPatients,
    createPatient,
    searchPatients,
    filterPatientsByDate,
    isLoading,
    error,
  } = usePatientsStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [isModalOpen, setModalOpen] = useState(false)
  const [isSubmitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [form, setForm] = useState({
    lastName: '',
    firstName: '',
    middleName: '',
    email: '',
    phone: '',
    birthday: '',
  })

  useEffect(() => {
    void fetchPatients()
  }, [fetchPatients])

  useEffect(() => {
    searchPatients(searchQuery)
  }, [searchQuery, searchPatients])

  useEffect(() => {
    filterPatientsByDate(startDate, endDate)
  }, [startDate, endDate, filterPatientsByDate])

  const canCreatePatient = user?.role === 'doctor' || user?.role === 'admin'

  const closeModal = () => {
    setModalOpen(false)
    setFormError(null)
    setForm({
      lastName: '',
      firstName: '',
      middleName: '',
      email: '',
      phone: '',
      birthday: '',
    })
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
    } catch (submitError: unknown) {
      const apiError = submitError as ApiError
      setFormError(apiError.response?.data?.detail || 'Не удалось создать карточку пациента')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Карточки пациентов</h1>
          <p className="text-gray-500">
            {user?.role === 'patient'
              ? 'Ваши доступные карточки и медицинские записи.'
              : 'Пациенты, к которым у вас есть доступ.'}
          </p>
        </div>
        {canCreatePatient && (
          <Button icon={<Plus className="h-5 w-5" />} onClick={() => setModalOpen(true)}>
            Добавить пациента
          </Button>
        )}
      </motion.div>

      <Card>
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <Input
            placeholder="Поиск по ФИО, email или телефону"
            icon={<Search className="h-5 w-5" />}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          <Input
            type="date"
            icon={<Calendar className="h-5 w-5" />}
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
          <Input
            type="date"
            icon={<Calendar className="h-5 w-5" />}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </div>

        {isLoading ? (
          <p className="py-20 text-center text-gray-500">Загружаю пациентов…</p>
        ) : error ? (
          <p className="py-20 text-center text-red-600">{error}</p>
        ) : filteredPatients.length === 0 ? (
          <p className="py-20 text-center text-gray-500">Доступных карточек пока нет.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {['Пациент', 'Дата рождения', 'Последняя запись', 'Записей', 'Действия'].map((header) => (
                    <th
                      key={header}
                      className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {filteredPatients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 font-medium text-primary-700">
                          {(patient.firstName[0] ?? '') + (patient.lastName[0] ?? '')}
                        </div>
                        <div className="ml-4">
                          <div className="font-medium text-gray-900">{patient.fio}</div>
                          <div className="text-sm text-gray-500">{patient.email || '—'}</div>
                          {patient.phone && <div className="text-sm text-gray-500">{patient.phone}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {patient.birthday ? format(new Date(patient.birthday), 'dd.MM.yyyy') : '—'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {patient.lastVisit ? format(new Date(patient.lastVisit), 'dd.MM.yyyy') : '—'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="flex items-center">
                        <FileText className="mr-1 h-4 w-4 text-gray-400" />
                        {patient.recordCount}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <Link to={`/patients/${patient.id}`} className="text-primary-600 hover:underline">
                        Открыть карточку
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-xl font-semibold">Новый пациент</h2>
            {formError && <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</p>}
            <div className="space-y-4">
              <Input name="lastName" label="Фамилия *" value={form.lastName} onChange={(event) => setForm({ ...form, lastName: event.target.value })} />
              <Input name="firstName" label="Имя *" value={form.firstName} onChange={(event) => setForm({ ...form, firstName: event.target.value })} />
              <Input name="middleName" label="Отчество" value={form.middleName} onChange={(event) => setForm({ ...form, middleName: event.target.value })} />
              <Input name="email" label="Email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
              <Input name="phone" label="Телефон" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
              <Input name="birthday" type="date" label="Дата рождения" value={form.birthday} onChange={(event) => setForm({ ...form, birthday: event.target.value })} />
            </div>
            <div className="mt-6 flex justify-end space-x-2">
              <Button variant="outline" onClick={closeModal}>Отмена</Button>
              <Button
                onClick={handleCreatePatient}
                disabled={isSubmitting || !form.firstName.trim() || !form.lastName.trim()}
              >
                {isSubmitting ? 'Сохраняю…' : 'Создать'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PatientListPage
