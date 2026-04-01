import React, { useState } from 'react'

import { useAuthStore } from '../stores/authStore'
import { usePatientsStore } from '../stores/patientsStore'
import { Button } from './common/Button'

interface Props {
  patientId: string
  onClose: () => void
}

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
}

const defaultPayload = '{\n  "details": ""\n}'

export const AddRecordModal: React.FC<Props> = ({ patientId, onClose }) => {
  const { user } = useAuthStore()
  const createPatientRecord = usePatientsStore((state) => state.createPatientRecord)

  const [recordType, setRecordType] = useState('consultation_result')
  const [eventDate, setEventDate] = useState(new Date().toISOString().slice(0, 10))
  const [title, setTitle] = useState('')
  const [appointmentLocation, setAppointmentLocation] = useState('')
  const [clinicalSummary, setClinicalSummary] = useState('')
  const [practitionerFullName, setPractitionerFullName] = useState('')
  const [practitionerSpecialty, setPractitionerSpecialty] = useState('')
  const [practitionerOrganization, setPractitionerOrganization] = useState('')
  const [practitionerPosition, setPractitionerPosition] = useState('')
  const [practitionerEmail, setPractitionerEmail] = useState('')
  const [practitionerPhone, setPractitionerPhone] = useState('')
  const [payloadText, setPayloadText] = useState(defaultPayload)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requiresPractitionerFields = user?.role !== 'doctor'

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)

    let payloadJson: Record<string, unknown>
    try {
      payloadJson = JSON.parse(payloadText) as Record<string, unknown>
    } catch {
      setError('Поле payload_json должно содержать корректный JSON')
      return
    }

    if (requiresPractitionerFields && !practitionerFullName.trim()) {
      setError('Укажите ФИО врача-автора записи')
      return
    }

    setLoading(true)
    try {
      await createPatientRecord(patientId, {
        record_type: recordType,
        event_date: eventDate,
        title: title || undefined,
        appointment_location: appointmentLocation || undefined,
        clinical_summary: clinicalSummary || undefined,
        payload_json: payloadJson,
        author_practitioner_full_name: requiresPractitionerFields
          ? practitionerFullName.trim()
          : undefined,
        author_practitioner_specialty: requiresPractitionerFields
          ? practitionerSpecialty || undefined
          : undefined,
        author_practitioner_organization: requiresPractitionerFields
          ? practitionerOrganization || undefined
          : undefined,
        author_practitioner_position: requiresPractitionerFields
          ? practitionerPosition || undefined
          : undefined,
        author_practitioner_email: requiresPractitionerFields
          ? practitionerEmail || undefined
          : undefined,
        author_practitioner_phone: requiresPractitionerFields
          ? practitionerPhone || undefined
          : undefined,
      })
      onClose()
    } catch (submitError: unknown) {
      const apiError = submitError as ApiError
      setError(apiError.response?.data?.detail || 'Не удалось создать запись')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-lg">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Новая медицинская запись</h2>
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-800">
            Закрыть
          </button>
        </div>

        {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Тип записи</span>
            <select
              value={recordType}
              onChange={(event) => setRecordType(event.target.value)}
              className="mt-1 w-full rounded border p-2"
            >
              <option value="consultation_result">Консультация</option>
              <option value="exam_result">Обследование</option>
              <option value="lab_result">Лаборатория</option>
              <option value="other">Другое</option>
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700">Дата события</span>
            <input
              type="date"
              value={eventDate}
              onChange={(event) => setEventDate(event.target.value)}
              className="mt-1 w-full rounded border p-2"
            />
          </label>

          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-gray-700">Заголовок</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-1 w-full rounded border p-2"
              placeholder="Например: Первичная консультация"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700">Место приёма</span>
            <input
              type="text"
              value={appointmentLocation}
              onChange={(event) => setAppointmentLocation(event.target.value)}
              className="mt-1 w-full rounded border p-2"
              placeholder="Клиника, кабинет, отделение"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700">Краткое клиническое резюме</span>
            <input
              type="text"
              value={clinicalSummary}
              onChange={(event) => setClinicalSummary(event.target.value)}
              className="mt-1 w-full rounded border p-2"
              placeholder="Краткий итог записи"
            />
          </label>

          {requiresPractitionerFields && (
            <>
              <label className="block md:col-span-2">
                <span className="text-sm font-medium text-gray-700">ФИО врача-автора</span>
                <input
                  type="text"
                  value={practitionerFullName}
                  onChange={(event) => setPractitionerFullName(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                  placeholder="Например: Иванов Иван Иванович"
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Специальность</span>
                <input
                  type="text"
                  value={practitionerSpecialty}
                  onChange={(event) => setPractitionerSpecialty(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Организация</span>
                <input
                  type="text"
                  value={practitionerOrganization}
                  onChange={(event) => setPractitionerOrganization(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Должность</span>
                <input
                  type="text"
                  value={practitionerPosition}
                  onChange={(event) => setPractitionerPosition(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Email врача</span>
                <input
                  type="email"
                  value={practitionerEmail}
                  onChange={(event) => setPractitionerEmail(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>

              <label className="block md:col-span-2">
                <span className="text-sm font-medium text-gray-700">Телефон врача</span>
                <input
                  type="text"
                  value={practitionerPhone}
                  onChange={(event) => setPractitionerPhone(event.target.value)}
                  className="mt-1 w-full rounded border p-2"
                />
              </label>
            </>
          )}

          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-gray-700">Типоспецифичные данные (JSON)</span>
            <textarea
              value={payloadText}
              onChange={(event) => setPayloadText(event.target.value)}
              rows={10}
              className="mt-1 w-full rounded border p-2 font-mono text-sm"
            />
          </label>
        </div>

        <div className="mt-6 flex justify-end space-x-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Отмена
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? 'Сохраняю…' : 'Создать запись'}
          </Button>
        </div>
      </form>
    </div>
  )
}
