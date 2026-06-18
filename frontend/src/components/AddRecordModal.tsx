import React, { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Building2,
  Calendar,
  Check,
  ChevronRight,
  ClipboardList,
  Code,
  FileText,
  Mail,
  Phone,
  Stethoscope,
  User,
  X,
} from 'lucide-react'

import { useAuthStore } from '../stores/authStore'
import { usePatientsStore } from '../stores/patientsStore'
import { Button } from './common/Button'

interface Props {
  patientId: string
  onClose: () => void
}

type ApiError = {
  response?: { data?: { detail?: string } }
}

type Step = 1 | 2 | 3

const defaultPayload = '{\n  "details": ""\n}'

const recordTypeOptions = [
  { value: 'consultation_result', label: 'Консультация', icon: <Stethoscope className="h-4 w-4" /> },
  { value: 'exam_result', label: 'Обследование', icon: <ClipboardList className="h-4 w-4" /> },
  { value: 'lab_result', label: 'Лаборатория', icon: <FileText className="h-4 w-4" /> },
  { value: 'other', label: 'Другое', icon: <FileText className="h-4 w-4" /> },
]

const steps = [
  { id: 1, title: 'Основная информация' },
  { id: 2, title: 'Врач-автор' },
  { id: 3, title: 'Данные записи (JSON)' },
]

export const AddRecordModal: React.FC<Props> = ({ patientId, onClose }) => {
  const { user } = useAuthStore()
  const createPatientRecord = usePatientsStore((state) => state.createPatientRecord)

  const [step, setStep] = useState<Step>(1)
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
  const totalSteps = requiresPractitionerFields ? 3 : 2

  const inputClass =
    'w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm placeholder-gray-400 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors'

  const fieldClass = 'block'
  const labelClass = 'mb-1.5 block text-sm font-medium text-gray-700'

  const handleNext = () => {
    if (step < (requiresPractitionerFields ? 3 : 2)) setStep((s) => (s + 1) as Step)
    else void handleSubmit()
  }

  const handleSubmit = async () => {
    setError(null)

    let payloadJson: Record<string, unknown>
    const normalizedPayloadText = payloadText.trim()
    try {
      payloadJson = normalizedPayloadText ? (JSON.parse(normalizedPayloadText) as Record<string, unknown>) : {}
    } catch {
      setError('Поле payload_json должно содержать корректный JSON')
      return
    }

    if (requiresPractitionerFields && !practitionerFullName.trim()) {
      setError('Укажите ФИО врача-автора')
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
        author_practitioner_full_name: requiresPractitionerFields ? practitionerFullName.trim() : undefined,
        author_practitioner_specialty: requiresPractitionerFields ? practitionerSpecialty || undefined : undefined,
        author_practitioner_organization: requiresPractitionerFields ? practitionerOrganization || undefined : undefined,
        author_practitioner_position: requiresPractitionerFields ? practitionerPosition || undefined : undefined,
        author_practitioner_email: requiresPractitionerFields ? practitionerEmail || undefined : undefined,
        author_practitioner_phone: requiresPractitionerFields ? practitionerPhone || undefined : undefined,
      })
      onClose()
    } catch (submitError: unknown) {
      const apiError = submitError as ApiError
      setError(apiError.response?.data?.detail || 'Не удалось создать запись')
    } finally {
      setLoading(false)
    }
  }

  const isLastStep = step === (requiresPractitionerFields ? 3 : 2)
  const canProceed =
    step === 1
      ? eventDate !== ''
      : step === 2 && requiresPractitionerFields
        ? practitionerFullName.trim() !== ''
        : true

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/60 p-4 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="relative w-full max-w-xl rounded-2xl bg-white shadow-xl overflow-hidden"
      >
        {/* Header */}
        <div className="border-b border-gray-100 bg-gray-50 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-gray-900">Новая медицинская запись</h2>
            <button type="button" onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:bg-gray-200">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Step progress */}
          <div className="flex items-center gap-1">
            {steps.slice(0, totalSteps).map((s, i) => (
              <React.Fragment key={s.id}>
                <div className="flex items-center gap-1.5">
                  <div
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                      step === s.id
                        ? 'bg-primary-600 text-white'
                        : step > s.id
                          ? 'bg-success-500 text-white'
                          : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {step > s.id ? <Check className="h-3.5 w-3.5" /> : s.id}
                  </div>
                  <span className={`hidden text-xs font-medium sm:block ${step === s.id ? 'text-primary-700' : 'text-gray-400'}`}>
                    {s.title}
                  </span>
                </div>
                {i < totalSteps - 1 && <ChevronRight className="h-3.5 w-3.5 text-gray-300 flex-shrink-0" />}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-5 scrollbar-thin">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <div>
                  <label className={labelClass}>Тип записи</label>
                  <div className="grid grid-cols-2 gap-2">
                    {recordTypeOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setRecordType(opt.value)}
                        className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium transition-all ${
                          recordType === opt.value
                            ? 'border-primary-300 bg-primary-50 text-primary-700'
                            : 'border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-300 hover:bg-white'
                        }`}
                      >
                        {opt.icon}
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className={labelClass}><span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5" /> Дата события *</span></label>
                  <input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} className={inputClass} />
                </div>

                <div>
                  <label className={labelClass}><span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Заголовок</span></label>
                  <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} placeholder="Например: Первичная консультация" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}><span className="flex items-center gap-1"><Building2 className="h-3.5 w-3.5" /> Место приёма</span></label>
                    <input type="text" value={appointmentLocation} onChange={(e) => setAppointmentLocation(e.target.value)} className={inputClass} placeholder="Клиника / кабинет" />
                  </div>
                  <div>
                    <label className={labelClass}>Клиническое резюме</label>
                    <input type="text" value={clinicalSummary} onChange={(e) => setClinicalSummary(e.target.value)} className={inputClass} placeholder="Краткий итог" />
                  </div>
                </div>
              </motion.div>
            )}

            {step === 2 && requiresPractitionerFields && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <p className="text-sm text-gray-500 -mt-1">Заполните данные врача, составившего запись.</p>
                <div>
                  <label className={labelClass}><span className="flex items-center gap-1"><User className="h-3.5 w-3.5" /> ФИО врача *</span></label>
                  <input type="text" value={practitionerFullName} onChange={(e) => setPractitionerFullName(e.target.value)} className={inputClass} placeholder="Иванов Иван Иванович" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}><span className="flex items-center gap-1"><Stethoscope className="h-3.5 w-3.5" /> Специальность</span></label>
                    <input type="text" value={practitionerSpecialty} onChange={(e) => setPractitionerSpecialty(e.target.value)} className={inputClass} placeholder="Кардиология" />
                  </div>
                  <div>
                    <label className={labelClass}>Должность</label>
                    <input type="text" value={practitionerPosition} onChange={(e) => setPractitionerPosition(e.target.value)} className={inputClass} placeholder="Ведущий специалист" />
                  </div>
                  <div>
                    <label className={labelClass}><span className="flex items-center gap-1"><Building2 className="h-3.5 w-3.5" /> Организация</span></label>
                    <input type="text" value={practitionerOrganization} onChange={(e) => setPractitionerOrganization(e.target.value)} className={inputClass} placeholder="ФГБУ «НМИЦ»" />
                  </div>
                  <div>
                    <label className={labelClass}><span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5" /> Email</span></label>
                    <input type="email" value={practitionerEmail} onChange={(e) => setPractitionerEmail(e.target.value)} className={inputClass} placeholder="doctor@clinic.ru" />
                  </div>
                  <div className="col-span-2">
                    <label className={labelClass}><span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5" /> Телефон</span></label>
                    <input type="text" value={practitionerPhone} onChange={(e) => setPractitionerPhone(e.target.value)} className={inputClass} placeholder="+7 (999) 000-00-00" />
                  </div>
                </div>
              </motion.div>
            )}

            {((step === 2 && !requiresPractitionerFields) || (step === 3 && requiresPractitionerFields)) && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-3"
              >
                <div className="flex items-center gap-2">
                  <Code className="h-4 w-4 text-gray-400" />
                  <label className="text-sm font-medium text-gray-700">Типоспецифичные данные (JSON)</label>
                </div>
                <p className="text-xs text-gray-400">
                  Дополнительные данные в формате JSON. Объект должен быть корректным.
                </p>
                <textarea
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                  rows={10}
                  className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 p-4 font-mono text-xs text-gray-800 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200"
                />
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <p className="mt-3 rounded-xl bg-error-50 px-4 py-2 text-sm text-error-700">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-6 py-4">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              if (step === 1) onClose()
              else setStep((s) => (s - 1) as Step)
            }}
            disabled={loading}
          >
            {step === 1 ? 'Отмена' : '← Назад'}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleNext}
            isLoading={loading}
            disabled={!canProceed || loading}
          >
            {isLastStep ? 'Создать запись' : 'Далее →'}
          </Button>
        </div>
      </motion.div>
    </motion.div>
  )
}
