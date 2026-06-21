import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Check, FileText, UserCheck } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { DateInput } from '../../components/common/DateInput'
import { Patient, usePatientsStore } from '../../stores/patientsStore'
import {
  ImportPatientDecision,
  ImportPatientDraft,
  ImportRecordGroupDecision,
  useUploadStore,
} from '../../stores/uploadStore'
import { formatDateForDisplay } from '../../utils/dates'

type PatientAction = 'existing' | 'create' | 'skip'

type GroupDecisionState = ImportRecordGroupDecision & {
  action: 'create' | 'skip'
}

type PatientDecisionState = {
  candidate_id: string
  action: PatientAction
  patient_passport_id: string
  fio: string
  date_of_birth: string
  record_groups: GroupDecisionState[]
}

type PatientOption = {
  id: string
  label: string
  priority: number
}

const recordTypeLabels: Record<string, string> = {
  exam_result: 'Обследование',
  lab_result: 'Анализ',
  consultation_result: 'Консультация',
  other: 'Другое',
}

const UploadReviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { currentJob, error, getJobById, resolveJob, isResolving } = useUploadStore()
  const {
    patients: accessiblePatients,
    fetchPatients,
    isLoading: isLoadingPatients,
    error: patientsError,
  } = usePatientsStore()
  const [decisions, setDecisions] = useState<PatientDecisionState[]>([])
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (jobId) void getJobById(jobId)
  }, [jobId, getJobById])

  useEffect(() => {
    void fetchPatients()
  }, [fetchPatients])

  const patientCandidates = useMemo(() => currentJob?.report_json.patients ?? [], [currentJob?.report_json.patients])
  const warnings = currentJob?.report_json.warnings ?? []

  useEffect(() => {
    if (decisions.length > 0 || patientCandidates.length === 0) return
    setDecisions(patientCandidates.map(toInitialDecision))
  }, [patientCandidates, decisions.length])

  if (!currentJob) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-gray-500">Загрузка черновика импорта...</p>
      </div>
    )
  }

  if (currentJob.status !== 'needs_review') {
    return (
      <div className="space-y-6">
        <Link to={`/upload/status/${currentJob.id}`} className="flex items-center text-sm text-primary-600 hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к статусу
        </Link>
        <Card>
          <p className="text-gray-700">Этот импорт уже не ожидает проверки.</p>
        </Card>
      </div>
    )
  }

  const submit = async () => {
    if (!jobId) return
    const validationError = validateDecisions(decisions)
    if (validationError) {
      setFormError(validationError)
      return
    }
    setFormError('')
    await resolveJob(jobId, decisions.map(toPayload))
    navigate(`/upload/status/${jobId}`)
  }

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Link to={`/upload/status/${currentJob.id}`} className="mb-2 flex items-center text-sm text-primary-600 hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к статусу
        </Link>
        <h1 className="text-2xl font-bold">Проверка импорта</h1>
        <p className="text-gray-500">Подтвердите, к каким карточкам пациентов добавить найденные записи.</p>
      </motion.div>

      {(formError || error || patientsError) && (
        <div className="flex items-start rounded-md border border-error-200 bg-error-50 p-3">
          <AlertTriangle className="mr-2 mt-0.5 h-5 w-5 flex-shrink-0 text-error-500" />
          <p className="text-sm text-error-700">{formError || error || patientsError}</p>
        </div>
      )}

      {decisions.map((decision, patientIndex) => {
        const patientCandidate = patientCandidates.find((item) => item.candidate_id === decision.candidate_id)
        if (!patientCandidate) return null
        const patientOptions = buildPatientOptions(accessiblePatients, patientCandidate)

        return (
          <Card key={decision.candidate_id} title={patientCandidate.fio ?? 'Пациент не распознан'}>
            <div className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-3">
                <label className="space-y-1">
                  <span className="text-sm font-medium text-gray-700">Решение</span>
                  <select
                    className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                    value={decision.action}
                    onChange={(event) => updatePatient(patientIndex, { action: event.target.value as PatientAction })}
                  >
                    <option value="create">Создать карточку</option>
                    <option value="existing">Добавить к существующей</option>
                    <option value="skip">Пропустить пациента</option>
                  </select>
                </label>

                {decision.action === 'create' && (
                  <>
                    <label className="space-y-1">
                      <span className="text-sm font-medium text-gray-700">ФИО</span>
                      <input
                        className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                        value={decision.fio}
                        onChange={(event) => updatePatient(patientIndex, { fio: event.target.value })}
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-sm font-medium text-gray-700">Дата рождения</span>
                      <DateInput
                        className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                        value={decision.date_of_birth}
                        onChange={(value) => updatePatient(patientIndex, { date_of_birth: value ?? '' })}
                      />
                    </label>
                  </>
                )}

                {decision.action === 'existing' && (
                  <label className="space-y-1 lg:col-span-2">
                    <span className="text-sm font-medium text-gray-700">Карточка пациента</span>
                    <select
                      className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                      value={decision.patient_passport_id}
                      disabled={isLoadingPatients}
                      onChange={(event) => updatePatient(patientIndex, { patient_passport_id: event.target.value })}
                    >
                      <option value="">
                        {isLoadingPatients ? 'Загрузка карточек...' : 'Выберите доступную карточку'}
                      </option>
                      {patientOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              {patientCandidate.existing_matches.length > 0 && decision.action === 'existing' && (
                <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <p className="mb-2 text-sm font-medium text-gray-700">Найденные совпадения</p>
                  <div className="space-y-2">
                    {patientCandidate.existing_matches.map((match) => (
                      <button
                        type="button"
                        key={match.id}
                        className="flex w-full items-center gap-3 rounded border border-gray-200 bg-white px-3 py-2 text-left text-sm hover:border-primary-300"
                        onClick={() => updatePatient(patientIndex, { patient_passport_id: match.id })}
                      >
                        <UserCheck className="h-4 w-4 text-primary-600" />
                        <span className="flex-1">
                          {match.fio}
                          {match.date_of_birth ? `, ${formatDateForDisplay(match.date_of_birth)}` : ''}
                        </span>
                        <span className="text-xs text-gray-500">{match.match_type === 'exact' ? 'точное' : 'похожее'}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {decision.record_groups.map((group, groupIndex) => {
                  const sourceGroup = patientCandidate.record_groups.find((item) => item.group_id === group.group_id)
                  return (
                    <div key={group.group_id} className="rounded-lg border border-gray-100 p-4">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-primary-600" />
                          <p className="font-medium text-gray-900">{group.title || sourceGroup?.title || 'Запись'}</p>
                        </div>
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={group.action === 'create'}
                            disabled={decision.action === 'skip'}
                            onChange={(event) => updateGroup(patientIndex, groupIndex, { action: event.target.checked ? 'create' : 'skip' })}
                          />
                          Импортировать
                        </label>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <label className="space-y-1">
                          <span className="text-xs font-medium text-gray-500">Тип</span>
                          <select
                            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                            value={group.record_type ?? 'other'}
                            disabled={decision.action === 'skip' || group.action === 'skip'}
                            onChange={(event) => updateGroup(patientIndex, groupIndex, { record_type: event.target.value })}
                          >
                            {Object.entries(recordTypeLabels).map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="space-y-1">
                          <span className="text-xs font-medium text-gray-500">Дата события</span>
                          <DateInput
                            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                            value={group.event_date ?? ''}
                            disabled={decision.action === 'skip' || group.action === 'skip'}
                            onChange={(value) => updateGroup(patientIndex, groupIndex, { event_date: value })}
                          />
                        </label>
                        <label className="space-y-1">
                          <span className="text-xs font-medium text-gray-500">Название</span>
                          <input
                            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                            value={group.title ?? ''}
                            disabled={decision.action === 'skip' || group.action === 'skip'}
                            onChange={(event) => updateGroup(patientIndex, groupIndex, { title: event.target.value })}
                          />
                        </label>
                      </div>

                      {sourceGroup && (
                        <p className="mt-3 text-xs text-gray-500">
                          Файлов: {sourceGroup.files.length}; DICOM: {sourceGroup.files.filter((file) => file.is_dicom).length}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </Card>
        )
      })}

      {warnings.length > 0 && (
        <Card title="Предупреждения" accent="warning">
          <ul className="space-y-2 text-sm text-gray-700">
            {warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex justify-end">
        <Button type="button" onClick={submit} isLoading={isResolving} icon={<Check className="h-4 w-4" />}>
          Подтвердить импорт
        </Button>
      </div>
    </div>
  )

  function updatePatient(index: number, patch: Partial<PatientDecisionState>) {
    setDecisions((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)))
  }

  function updateGroup(patientIndex: number, groupIndex: number, patch: Partial<GroupDecisionState>) {
    setDecisions((current) =>
      current.map((patient, itemIndex) => {
        if (itemIndex !== patientIndex) return patient
        return {
          ...patient,
          record_groups: patient.record_groups.map((group, innerIndex) => (
            innerIndex === groupIndex ? { ...group, ...patch } : group
          )),
        }
      }),
    )
  }
}

function buildPatientOptions(accessiblePatients: Patient[], patientCandidate: ImportPatientDraft): PatientOption[] {
  const matchTypeById = new Map(patientCandidate.existing_matches.map((match) => [match.id, match.match_type]))
  return accessiblePatients
    .map((patient) => {
      const matchType = matchTypeById.get(patient.id)
      const matchLabel = matchType === 'exact' ? 'точное совпадение' : matchType === 'fuzzy' ? 'похожая карточка' : ''
      return {
        id: patient.id,
        priority: matchType === 'exact' ? 0 : matchType === 'fuzzy' ? 1 : 2,
        label: [
          patient.fio,
          patient.birthday ? formatDateForDisplay(patient.birthday) : '',
          matchLabel,
        ].filter(Boolean).join(', '),
      }
    })
    .sort((left, right) => left.priority - right.priority || left.label.localeCompare(right.label))
}

function toInitialDecision(patient: ImportPatientDraft): PatientDecisionState {
  const exactMatch = patient.existing_matches.find((match) => match.match_type === 'exact')
  return {
    candidate_id: patient.candidate_id,
    action: exactMatch ? 'existing' : 'create',
    patient_passport_id: exactMatch?.id ?? '',
    fio: patient.fio ?? '',
    date_of_birth: patient.date_of_birth ?? '',
    record_groups: patient.record_groups.map((group) => ({
      group_id: group.group_id,
      action: 'create',
      record_type: group.record_type,
      event_date: group.event_date,
      title: group.title,
    })),
  }
}

function validateDecisions(decisions: PatientDecisionState[]): string {
  for (const decision of decisions) {
    if (decision.action === 'skip') continue
    if (decision.action === 'existing' && !decision.patient_passport_id) {
      return 'Выберите существующую карточку пациента или создайте новую.'
    }
    if (decision.action === 'create' && !decision.fio.trim()) {
      return 'Укажите ФИО для новой карточки пациента.'
    }
  }
  return ''
}

function toPayload(decision: PatientDecisionState): ImportPatientDecision {
  return {
    candidate_id: decision.candidate_id,
    action: decision.action,
    patient_passport_id: decision.action === 'existing' ? decision.patient_passport_id : undefined,
    fio: decision.action === 'create' ? decision.fio.trim() : undefined,
    date_of_birth: decision.action === 'create' ? decision.date_of_birth || null : undefined,
    record_groups: decision.record_groups.map((group) => ({
      group_id: group.group_id,
      action: group.action,
      record_type: group.record_type,
      event_date: group.event_date || null,
      title: group.title,
    })),
  }
}

export default UploadReviewPage
