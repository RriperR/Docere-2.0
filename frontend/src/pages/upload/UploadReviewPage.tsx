import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Check, FileText, RotateCcw, UserCheck } from 'lucide-react'

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
import { groupedWarnings, warningAffectsFile } from '../../utils/importWarnings'

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

type BulkPatchState = {
  record_type: string
  event_date: string
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
  const {
    currentJob,
    error,
    getJobById,
    resolveJob,
    saveReviewDraft,
    isResolving,
    isSavingReviewDraft,
    reviewDraftError,
  } = useUploadStore()
  const {
    patients: accessiblePatients,
    fetchPatients,
    isLoading: isLoadingPatients,
    error: patientsError,
  } = usePatientsStore()
  const [decisions, setDecisions] = useState<PatientDecisionState[]>([])
  const [formError, setFormError] = useState('')
  const [selectedGroupsByPatient, setSelectedGroupsByPatient] = useState<Record<string, string[]>>({})
  const [bulkPatchByPatient, setBulkPatchByPatient] = useState<Record<string, BulkPatchState>>({})
  const [initializedJobId, setInitializedJobId] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const lastSavedSnapshot = useRef('')
  const lastAttemptedSnapshot = useRef('')

  useEffect(() => {
    if (jobId) void getJobById(jobId)
  }, [jobId, getJobById])

  useEffect(() => {
    void fetchPatients()
  }, [fetchPatients])

  const patientCandidates = useMemo(() => currentJob?.report_json.patients ?? [], [currentJob?.report_json.patients])
  const warnings = currentJob?.report_json.warnings ?? []
  const warningViews = groupedWarnings(warnings)

  useEffect(() => {
    if (!jobId || currentJob?.id !== jobId || initializedJobId === jobId) return
    const restored = restoreDecisions(patientCandidates, currentJob.review_decisions ?? [])
    setDecisions(restored)
    setLastSavedAt(currentJob.review_updated_at)
    lastSavedSnapshot.current = JSON.stringify(restored.map(toPayload))
    lastAttemptedSnapshot.current = lastSavedSnapshot.current
    setInitializedJobId(jobId)
  }, [currentJob, initializedJobId, jobId, patientCandidates])

  useEffect(() => {
    if (
      !jobId ||
      initializedJobId !== jobId ||
      currentJob?.status !== 'needs_review' ||
      isResolving ||
      isSavingReviewDraft
    ) return
    const payload = decisions.map(toPayload)
    const snapshot = JSON.stringify(payload)
    if (snapshot === lastSavedSnapshot.current || snapshot === lastAttemptedSnapshot.current) return

    const timer = window.setTimeout(() => {
      lastAttemptedSnapshot.current = snapshot
      void saveReviewDraft(jobId, payload)
        .then((updatedAt) => {
          lastSavedSnapshot.current = snapshot
          setLastSavedAt(updatedAt)
        })
        .catch(() => undefined)
    }, 700)
    return () => window.clearTimeout(timer)
  }, [
    currentJob?.status,
    decisions,
    initializedJobId,
    isResolving,
    isSavingReviewDraft,
    jobId,
    saveReviewDraft,
  ])

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

  const reviewTotals = patientCandidates.reduce((totals, patient) => {
    const decision = decisions.find((item) => item.candidate_id === patient.candidate_id)
    const summary = reviewSummary(patient, decision)
    const hasPatientIssue = !decision
      || (decision.action === 'existing' && !decision.patient_passport_id)
      || (decision.action === 'create' && !decision.fio.trim())
    return {
      ready: totals.ready + summary.ready,
      unresolved: totals.unresolved + summary.needsDate + summary.needsDuplicate + (hasPatientIssue ? 1 : 0),
      skipped: totals.skipped + summary.skipped,
    }
  }, { ready: 0, unresolved: 0, skipped: 0 })
  const firstReviewIssueAnchor = findFirstReviewIssueAnchor(patientCandidates, decisions)

  const submit = async () => {
    if (!jobId) return
    const validationError = validateDecisions(decisions, patientCandidates)
    if (validationError) {
      setFormError(validationError)
      return
    }
    const selectedPatients = decisions.filter((decision) => decision.action !== 'skip').length
    const selectedRecords = decisions.reduce(
      (count, decision) => count + decision.record_groups.filter((group) => group.action === 'create').length,
      0,
    )
    if (!window.confirm(`Подтвердить импорт: пациентов — ${selectedPatients}, записей — ${selectedRecords}?`)) return
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
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
          <span>
            {isSavingReviewDraft
              ? 'Сохранение черновика…'
              : lastSavedAt
                ? `Черновик сохранён ${new Date(lastSavedAt).toLocaleString('ru-RU')}`
                : 'Черновик без изменений'}
          </span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            icon={<RotateCcw className="h-3.5 w-3.5" />}
            onClick={resetReviewDraft}
          >
            Сбросить решения
          </Button>
        </div>
      </motion.div>

      {(formError || error || patientsError || reviewDraftError) && (
        <div className="flex items-start rounded-md border border-error-200 bg-error-50 p-3">
          <AlertTriangle className="mr-2 mt-0.5 h-5 w-5 flex-shrink-0 text-error-500" />
          <p className="text-sm text-error-700">{formError || error || patientsError || reviewDraftError}</p>
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="flex flex-wrap gap-4">
            <span className="font-medium text-success-700">Готово: {reviewTotals.ready}</span>
            <span className={reviewTotals.unresolved > 0 ? 'font-medium text-warning-700' : 'text-gray-500'}>
              Требуют решения: {reviewTotals.unresolved}
            </span>
            <span className="text-gray-500">Пропущено: {reviewTotals.skipped}</span>
          </div>
          {firstReviewIssueAnchor && (
            <a className="font-medium text-primary-700 hover:underline" href={`#${firstReviewIssueAnchor}`}>
              Перейти к следующему вопросу
            </a>
          )}
        </div>
      </Card>

      {patientCandidates.length > 0 && (
        <div className="sticky top-0 z-10 rounded-md border border-gray-100 bg-white/95 p-3 shadow-sm backdrop-blur">
          <div className="flex flex-wrap gap-2">
            {patientCandidates.map((patient) => {
              const decision = decisions.find((item) => item.candidate_id === patient.candidate_id)
              const summary = reviewSummary(patient, decision)
              return (
                <a
                  key={patient.candidate_id}
                  href={`#${patient.candidate_id}`}
                  className="rounded border border-gray-200 px-3 py-2 text-sm hover:border-primary-300"
                >
                  <span className="font-medium text-gray-900">{patient.fio ?? 'Пациент не распознан'}</span>
                  <span className="ml-2 text-xs text-gray-500">
                    готово {summary.ready} · даты {summary.needsDate} · дубли {summary.needsDuplicate} · пропущено {summary.skipped}
                  </span>
                </a>
              )
            })}
          </div>
        </div>
      )}

      {decisions.map((decision, patientIndex) => {
        const patientCandidate = patientCandidates.find((item) => item.candidate_id === decision.candidate_id)
        if (!patientCandidate) return null
        const patientOptions = buildPatientOptions(accessiblePatients, patientCandidate)

        return (
          <Card key={decision.candidate_id} title={patientCandidate.fio ?? 'Пациент не распознан'}>
            <div id={decision.candidate_id} className="scroll-mt-24" />
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
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => updateAllGroups(patientIndex, { action: 'create' })}>
                    Импортировать все
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => updateAllGroups(patientIndex, { action: 'skip' })}>
                    Пропустить все
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => applyFirstDateCandidates(patientIndex, patientCandidate)}>
                    Применить найденные даты
                  </Button>
                </div>
                <div className="grid gap-3 rounded-md border border-gray-100 bg-gray-50 p-3 md:grid-cols-[minmax(160px,1fr)_minmax(180px,1fr)_auto_auto] md:items-end">
                  <label className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Тип для выбранных</span>
                    <select
                      className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                      value={getBulkPatch(decision.candidate_id).record_type}
                      onChange={(event) => updateBulkPatch(decision.candidate_id, { record_type: event.target.value })}
                    >
                      {Object.entries(recordTypeLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Дата для выбранных</span>
                    <DateInput
                      className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                      value={getBulkPatch(decision.candidate_id).event_date}
                      onChange={(value) => updateBulkPatch(decision.candidate_id, { event_date: value ?? '' })}
                    />
                  </label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={getSelectedGroupIds(decision.candidate_id).length === 0}
                    onClick={() => applyToSelectedGroups(patientIndex, decision.candidate_id, { record_type: getBulkPatch(decision.candidate_id).record_type })}
                  >
                    Применить тип
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={getSelectedGroupIds(decision.candidate_id).length === 0 || !getBulkPatch(decision.candidate_id).event_date}
                    onClick={() => applyToSelectedGroups(patientIndex, decision.candidate_id, { event_date: getBulkPatch(decision.candidate_id).event_date })}
                  >
                    Применить дату
                  </Button>
                </div>
                {decision.record_groups.map((group, groupIndex) => {
                  const sourceGroup = patientCandidate.record_groups.find((item) => item.group_id === group.group_id)
                  const needsDate = group.action === 'create' && !group.event_date
                  const duplicateCandidates = getRelevantDuplicateCandidates(sourceGroup, decision)
                  const hasDuplicates = duplicateCandidates.length > 0
                  const needsDuplicateConfirmation = hasDuplicates && group.action === 'create' && !group.allow_possible_duplicate
                  const isSelected = getSelectedGroupIds(decision.candidate_id).includes(group.group_id)
                  return (
                    <div
                      key={group.group_id}
                      id={`review-group-${group.group_id}`}
                      className="scroll-mt-28 rounded-lg border border-gray-100 p-4"
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-primary-600" />
                          <p className="font-medium text-gray-900">{group.title || sourceGroup?.title || 'Запись'}</p>
                          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${group.action === 'skip' ? 'border-gray-200 bg-gray-50 text-gray-600' : needsDate || needsDuplicateConfirmation ? 'border-warning-200 bg-warning-50 text-warning-700' : 'border-success-200 bg-success-50 text-success-700'}`}>
                            {group.action === 'skip' ? 'Пропущено' : needsDate ? 'Нужно выбрать дату' : needsDuplicateConfirmation ? 'Нужно решить по дублю' : 'Готово'}
                          </span>
                          {hasDuplicates && (
                            <span className="rounded-full border border-warning-200 bg-warning-50 px-2 py-0.5 text-xs font-medium text-warning-700">
                              {group.allow_possible_duplicate ? 'Дубль подтверждён' : 'Возможный дубль'}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-3">
                          <label className="flex items-center gap-2 text-sm text-gray-700">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(event) => toggleGroupSelection(decision.candidate_id, group.group_id, event.target.checked)}
                            />
                            Выбрано
                          </label>
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
                      </div>

                      {duplicateCandidates.length > 0 && (
                        <div className="mb-3 rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
                          <p className="font-medium">Похожие записи уже есть у пациента</p>
                          <div className="mt-2 space-y-1">
                            {duplicateCandidates.map((candidate) => (
                              <div key={candidate.record_id} className="flex flex-wrap items-center gap-2 text-xs">
                                <span>{candidate.title || 'Медицинская запись'}</span>
                                <span>{recordTypeLabels[candidate.record_type] ?? candidate.record_type}</span>
                                <span>{formatDateForDisplay(candidate.event_date)}</span>
                                <span className="text-warning-700">
                                  совпадают дата и название
                                </span>
                                <Link
                                  to={`/patients/${candidate.patient_passport_id}`}
                                  className="font-medium text-primary-700 hover:underline"
                                >
                                  Открыть карточку
                                </Link>
                              </div>
                            ))}
                          </div>
                          {group.action === 'create' && (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant={group.allow_possible_duplicate ? 'outline' : 'primary'}
                                onClick={() => updateGroup(patientIndex, groupIndex, { allow_possible_duplicate: !group.allow_possible_duplicate })}
                              >
                                {group.allow_possible_duplicate ? 'Отменить подтверждение' : 'Импортировать всё равно'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => updateGroup(patientIndex, groupIndex, { action: 'skip' })}
                              >
                                Пропустить запись
                              </Button>
                            </div>
                          )}
                        </div>
                      )}

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
                            className={`w-full rounded-md border px-3 py-2 text-sm ${
                              needsDate ? 'border-warning-300 bg-warning-50' : 'border-gray-200'
                            }`}
                            value={group.event_date ?? ''}
                            disabled={decision.action === 'skip' || group.action === 'skip'}
                            onChange={(value) => updateGroup(patientIndex, groupIndex, { event_date: value })}
                          />
                          {sourceGroup && sourceGroup.event_date_candidates.length > 1 && (
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {sourceGroup.event_date_candidates.map((candidate) => {
                                const selected = group.event_date === candidate
                                return (
                                  <button
                                    type="button"
                                    key={`${group.group_id}-${candidate}`}
                                    disabled={decision.action === 'skip' || group.action === 'skip'}
                                    className={[
                                      'rounded border px-2 py-1 text-xs transition-colors',
                                      selected
                                        ? 'border-primary-500 bg-primary-50 text-primary-700'
                                        : 'border-gray-200 bg-white text-gray-600 hover:border-primary-300',
                                    ].join(' ')}
                                    onClick={() => updateGroup(patientIndex, groupIndex, { event_date: candidate })}
                                  >
                                    {formatDateForDisplay(candidate)}
                                  </button>
                                )
                              })}
                            </div>
                          )}
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
                        <div className="mt-3 space-y-2">
                          <p className="text-xs text-gray-500">
                            Файлов: {sourceGroup.files.length}; DICOM: {sourceGroup.files.filter((file) => file.is_dicom).length}
                          </p>
                          <div className="grid gap-2 md:grid-cols-2">
                            {sourceGroup.files.map((file) => {
                              const hasWarning = warningAffectsFile(warnings, file.path, file.filename)
                              return (
                                <div key={file.path} className="rounded border border-gray-100 bg-gray-50 px-3 py-2 text-xs">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="truncate font-medium text-gray-800">{file.filename}</span>
                                    <span className="shrink-0 text-gray-500">{formatFileSize(file.size_bytes)}</span>
                                  </div>
                                  <div className="mt-1 flex flex-wrap gap-2 text-gray-500">
                                    <span>{file.is_dicom ? 'DICOM' : file.mime_type}</span>
                                    {hasWarning && <span className="text-warning-700">есть warning</span>}
                                  </div>
                                  <p className="mt-1 break-all text-gray-400">{file.path}</p>
                                </div>
                              )
                            })}
                          </div>
                        </div>
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
          <div className="space-y-3 text-sm">
            {warningViews.map((view) => {
              return (
                <div key={view.label} className="space-y-2">
                  <span className={`rounded border px-2 py-0.5 text-xs font-medium ${view.tone}`}>
                    {view.label}: {view.warnings.length}
                  </span>
                  <ul className="space-y-1 text-gray-700">
                    {view.warnings.map((warning, index) => (
                      <li key={`${warning}-${index}`} className="break-words">{warning}</li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
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
    setDecisions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item
      const resetsDuplicateDecision = patch.action !== undefined || patch.patient_passport_id !== undefined
      return {
        ...item,
        ...patch,
        record_groups: resetsDuplicateDecision
          ? item.record_groups.map((group) => ({ ...group, allow_possible_duplicate: false }))
          : item.record_groups,
      }
    }))
  }

  function updateGroup(patientIndex: number, groupIndex: number, patch: Partial<GroupDecisionState>) {
    setDecisions((current) =>
      current.map((patient, itemIndex) => {
        if (itemIndex !== patientIndex) return patient
        return {
          ...patient,
          record_groups: patient.record_groups.map((group, innerIndex) => (
            innerIndex === groupIndex
              ? {
                  ...group,
                  ...patch,
                  allow_possible_duplicate:
                    patch.record_type !== undefined || patch.event_date !== undefined || patch.title !== undefined
                      ? false
                      : patch.allow_possible_duplicate ?? group.allow_possible_duplicate,
                }
              : group
          )),
        }
      }),
    )
  }

  function updateAllGroups(patientIndex: number, patch: Partial<GroupDecisionState>) {
    setDecisions((current) =>
      current.map((patient, itemIndex) => (
        itemIndex === patientIndex
          ? { ...patient, record_groups: patient.record_groups.map((group) => ({ ...group, ...patch })) }
          : patient
      )),
    )
  }

  function getSelectedGroupIds(candidateId: string) {
    return selectedGroupsByPatient[candidateId] ?? []
  }

  function getBulkPatch(candidateId: string) {
    return bulkPatchByPatient[candidateId] ?? { record_type: 'other', event_date: '' }
  }

  function updateBulkPatch(candidateId: string, patch: Partial<BulkPatchState>) {
    setBulkPatchByPatient((current) => ({
      ...current,
      [candidateId]: { ...getBulkPatch(candidateId), ...patch },
    }))
  }

  function toggleGroupSelection(candidateId: string, groupId: string, selected: boolean) {
    setSelectedGroupsByPatient((current) => {
      const groupIds = current[candidateId] ?? []
      const nextGroupIds = selected
        ? Array.from(new Set([...groupIds, groupId]))
        : groupIds.filter((item) => item !== groupId)
      return { ...current, [candidateId]: nextGroupIds }
    })
  }

  function applyToSelectedGroups(patientIndex: number, candidateId: string, patch: Partial<GroupDecisionState>) {
    const selectedGroupIds = getSelectedGroupIds(candidateId)
    if (selectedGroupIds.length === 0) return
    setDecisions((current) =>
      current.map((patient, itemIndex) => {
        if (itemIndex !== patientIndex) return patient
        return {
          ...patient,
          record_groups: patient.record_groups.map((group) => (
            selectedGroupIds.includes(group.group_id)
              ? {
                  ...group,
                  ...patch,
                  allow_possible_duplicate:
                    patch.record_type !== undefined || patch.event_date !== undefined || patch.title !== undefined
                      ? false
                      : patch.allow_possible_duplicate ?? group.allow_possible_duplicate,
                }
              : group
          )),
        }
      }),
    )
  }

  function applyFirstDateCandidates(patientIndex: number, patient: ImportPatientDraft) {
    setDecisions((current) =>
      current.map((decision, itemIndex) => {
        if (itemIndex !== patientIndex) return decision
        return {
          ...decision,
          record_groups: decision.record_groups.map((group) => {
            const sourceGroup = patient.record_groups.find((item) => item.group_id === group.group_id)
            const firstCandidate = sourceGroup?.event_date_candidates[0]
            return firstCandidate && !group.event_date
              ? { ...group, event_date: firstCandidate, allow_possible_duplicate: false }
              : group
          }),
        }
      }),
    )
  }

  function resetReviewDraft() {
    if (!window.confirm('Сбросить все решения по этому архиву?')) return
    setDecisions(patientCandidates.map(toInitialDecision))
    setSelectedGroupsByPatient({})
    setBulkPatchByPatient({})
    setFormError('')
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
      allow_possible_duplicate: false,
    })),
  }
}

function restoreDecisions(
  patients: ImportPatientDraft[],
  savedDecisions: ImportPatientDecision[],
): PatientDecisionState[] {
  const savedByCandidate = new Map(savedDecisions.map((decision) => [decision.candidate_id, decision]))
  return patients.map((patient) => {
    const initial = toInitialDecision(patient)
    const saved = savedByCandidate.get(patient.candidate_id)
    if (!saved) return initial
    const savedGroups = new Map(saved.record_groups.map((group) => [group.group_id, group]))
    return {
      ...initial,
      action: saved.action,
      patient_passport_id: saved.patient_passport_id ?? '',
      fio: saved.fio ?? initial.fio,
      date_of_birth: saved.date_of_birth ?? '',
      record_groups: initial.record_groups.map((group) => {
        const savedGroup = savedGroups.get(group.group_id)
        return savedGroup
          ? {
              ...group,
              ...savedGroup,
              event_date: savedGroup.event_date ?? null,
              allow_possible_duplicate: savedGroup.allow_possible_duplicate ?? false,
            }
          : group
      }),
    }
  })
}

function validateDecisions(decisions: PatientDecisionState[], patients: ImportPatientDraft[]): string {
  for (const decision of decisions) {
    if (decision.action === 'skip') continue
    if (decision.action === 'existing' && !decision.patient_passport_id) {
      return 'Выберите существующую карточку пациента или создайте новую.'
    }
    if (decision.action === 'create' && !decision.fio.trim()) {
      return 'Укажите ФИО для новой карточки пациента.'
    }
    for (const group of decision.record_groups) {
      const patient = patients.find((item) => item.candidate_id === decision.candidate_id)
      const sourceGroup = patient?.record_groups.find((item) => item.group_id === group.group_id)
      if (group.action === 'create' && !group.event_date) {
        return 'Укажите дату события для каждой импортируемой медицинской записи.'
      }
      if (
        group.action === 'create' &&
        getRelevantDuplicateCandidates(sourceGroup, decision).length > 0 &&
        !group.allow_possible_duplicate
      ) {
        return 'Для возможного дубля выберите «Импортировать всё равно» или пропустите запись.'
      }
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
      allow_possible_duplicate: group.allow_possible_duplicate ?? false,
    })),
  }
}

function getRelevantDuplicateCandidates(
  sourceGroup: ImportPatientDraft['record_groups'][number] | undefined,
  decision: PatientDecisionState,
) {
  if (!sourceGroup || decision.action !== 'existing' || !decision.patient_passport_id) return []
  return sourceGroup.duplicate_candidates.filter(
    (candidate) => candidate.patient_passport_id === decision.patient_passport_id,
  )
}

function reviewSummary(patient: ImportPatientDraft, decision: PatientDecisionState | undefined) {
  if (!decision) return { ready: 0, needsDate: 0, needsDuplicate: 0, skipped: 0 }
  return decision.record_groups.reduce((summary, group) => {
    const sourceGroup = patient.record_groups.find((item) => item.group_id === group.group_id)
    if (group.action === 'skip') return { ...summary, skipped: summary.skipped + 1 }
    if (!group.event_date) {
      return { ...summary, needsDate: summary.needsDate + 1 }
    }
    if (getRelevantDuplicateCandidates(sourceGroup, decision).length > 0 && !group.allow_possible_duplicate) {
      return { ...summary, needsDuplicate: summary.needsDuplicate + 1 }
    }
    return { ...summary, ready: summary.ready + 1 }
  }, { ready: 0, needsDate: 0, needsDuplicate: 0, skipped: 0 })
}

function findFirstReviewIssueAnchor(
  patients: ImportPatientDraft[],
  decisions: PatientDecisionState[],
): string | null {
  for (const decision of decisions) {
    if (decision.action === 'skip') continue
    const patient = patients.find((item) => item.candidate_id === decision.candidate_id)
    if (
      (decision.action === 'existing' && !decision.patient_passport_id)
      || (decision.action === 'create' && !decision.fio.trim())
    ) {
      return decision.candidate_id
    }
    for (const group of decision.record_groups) {
      if (group.action === 'skip') continue
      const sourceGroup = patient?.record_groups.find((item) => item.group_id === group.group_id)
      const hasUnconfirmedDuplicate =
        getRelevantDuplicateCandidates(sourceGroup, decision).length > 0 && !group.allow_possible_duplicate
      if (!group.event_date || hasUnconfirmedDuplicate) return `review-group-${group.group_id}`
    }
  }
  return null
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 Б'
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export default UploadReviewPage
