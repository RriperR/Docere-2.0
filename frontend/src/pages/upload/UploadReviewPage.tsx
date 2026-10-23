import axios from 'axios'
import api from '../../api/api'
import { AiFieldName, AppliedAi, aiErrorLabels, aiStatusLabels } from '../../api/importAi'
import AiSuggestions from './AiSuggestions'
import { useImportAi } from './useImportAi'
import { UploadJob } from '../../stores/uploadStore'
import DocumentViewer from '../../components/records/DocumentViewer'
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
import { PatientImportContext } from './PatientImportContext'
import { usePatientImportContext } from './usePatientImportContext'
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
  const context = usePatientImportContext()
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
  const [previewFile, setPreviewFile] = useState<string | null>(null)
  const [previewPage, setPreviewPage] = useState(1)
  const previewPanel = useRef<HTMLDivElement>(null)
  const previewTrigger = useRef<HTMLElement | null>(null)
  const restorePreviewTrigger = useRef(false)
  const [mobileTab, setMobileTab] = useState<'fields' | 'document'>('fields')
  const [aiSelection, setAiSelection] = useState<string[]>([])
  const [regrouping, setRegrouping] = useState(false)
  const ai = useImportAi(currentJob)
  const accessLost = React.useCallback(async () => { setPreviewFile(null); if (jobId) await getJobById(jobId) }, [jobId, getJobById])
  const [serverDuplicates, setServerDuplicates] = useState<string[]>([])
  const [selectedGroupsByPatient, setSelectedGroupsByPatient] = useState<Record<string, string[]>>({})
  const [bulkPatchByPatient, setBulkPatchByPatient] = useState<Record<string, BulkPatchState>>({})
  const [initializedJobId, setInitializedJobId] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const lastSavedSnapshot = useRef('')
  const lastAttemptedSnapshot = useRef('')

  useEffect(() => {
    if (restorePreviewTrigger.current && (!previewFile || mobileTab === 'fields')) {
      restorePreviewTrigger.current = false
      if (previewTrigger.current?.isConnected) {
        previewTrigger.current.scrollIntoView?.({ block: 'center', behavior: 'instant' })
        previewTrigger.current.focus({ preventScroll: true })
      }
      return
    }
    if (!previewFile || mobileTab !== 'document') return
    previewPanel.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    previewPanel.current?.focus({ preventScroll: true })
  }, [previewFile, previewPage, mobileTab])

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
      isSavingReviewDraft || regrouping
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
    regrouping,
  ])

  if (!currentJob || currentJob.id !== jobId) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div>{error ? <p role="alert" className="text-red-700">{error} <button className="underline" onClick={() => jobId && void getJobById(jobId)}>Повторить</button></p> : <p className="text-gray-500">Загрузка черновика импорта...</p>}</div>
      </div>
    )
  }

  if (currentJob.status !== 'needs_review') {
    return (
      <div className="space-y-6">
        <Link to={`/upload/status/${currentJob.id}${context.query}`} className="flex items-center text-sm text-primary-600 hover:underline">
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
      unresolved: totals.unresolved + summary.needsDate + summary.needsDuplicate + (hasPatientIssue ? 1 : 0)
        + (decision?.record_groups.filter(group => serverDuplicates.includes(group.group_id)
          && group.action === 'create' && !group.allow_possible_duplicate
          && !getRelevantDuplicateCandidates(patient.record_groups.find(source => source.group_id === group.group_id), decision).length).length ?? 0),
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
    if (decisions.some(patient => patient.action !== 'skip' && patient.record_groups.some(group =>
      serverDuplicates.includes(group.group_id) && group.action === 'create' && !group.allow_possible_duplicate))) {
      setFormError('Решите, импортировать найденный сервером дубль или пропустить запись.')
      return
    }
    const selectedPatients = decisions.filter((decision) => decision.action !== 'skip').length
    const selectedRecords = decisions.reduce(
      (count, decision) => count + decision.record_groups.filter((group) => group.action === 'create').length,
      0,
    )
    if (!window.confirm(`Подтвердить импорт: пациентов — ${selectedPatients}, записей — ${selectedRecords}?`)) return
    setFormError('')
    try {
      await resolveJob(jobId, decisions.map(toPayload))
      navigate(`/upload/status/${jobId}${context.query}`)
    } catch (cause: unknown) {
      const detail: unknown = axios.isAxiosError(cause) ? cause.response?.data?.detail : null
      if (detail && typeof detail === 'object' && 'code' in detail && detail.code === 'duplicate_confirmation_required'
        && 'group_id' in detail && typeof detail.group_id === 'string') {
        const groupId = detail.group_id
        setServerDuplicates(current => [...new Set([...current, groupId])])
        setFormError('Сервер нашёл похожую запись после изменения данных. Проверьте отмеченную группу.')
        document.getElementById(`review-group-${groupId}`)?.scrollIntoView?.({ block: 'center' })
      }
      // Store показывает остальные ошибки. Решения и текст формы остаются на месте.
    }
  }

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Link to={`/upload/status/${currentJob.id}${context.query}`} className="mb-2 flex items-center text-sm text-primary-600 hover:underline">
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

      <PatientImportContext context={context} />

      {(formError || error || patientsError || reviewDraftError) && (
        <div className="flex items-start rounded-md border border-error-200 bg-error-50 p-3">
          <AlertTriangle className="mr-2 mt-0.5 h-5 w-5 shrink-0 text-error-500" />
          <p role="alert" className="text-sm text-error-700">{error === 'Network Error' && !formError ? 'Не удалось подтвердить импорт. Проверьте соединение и повторите. Ваши решения остались в форме.' : formError || error || patientsError || reviewDraftError}</p>
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
        <div className="sticky top-0 z-10 rounded-md border border-gray-100 bg-white/95 p-3 shadow-xs backdrop-blur-sm">
          <div className="flex flex-wrap gap-2">
            {patientCandidates.map((patient) => {
              const decision = decisions.find((item) => item.candidate_id === patient.candidate_id)
              const summary = reviewSummary(patient, decision)
              return (
                <a
                  key={patient.candidate_id}
                  href={`#${patient.candidate_id}`}
                  className="rounded-sm border border-gray-200 px-3 py-2 text-sm hover:border-primary-300"
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

      <Card title="AI-помощник импорта">
        <p className="mb-3 text-sm text-gray-600">Выберите документы для передачи внешнему сервису. AI предлагает факты; вы проверяете оригиналы и решаете, какие поля применить.</p>
        {ai.capabilities?.enabled && <p className="text-xs text-gray-500">До {ai.capabilities.max_documents} документов и {ai.capabilities.max_pages} страниц за запуск; до {ai.capabilities.max_pages_per_document} страниц в одном документе.</p>}
        {!ai.capabilities?.enabled && <p className="text-sm text-gray-500">AI-сервис пока не настроен. Обычный импорт доступен.</p>}
        <div className="my-3 grid gap-2 md:grid-cols-2">{patientCandidates.flatMap(p => p.record_groups.flatMap(g => g.files)).filter(f => f.id && !f.is_dicom && ['application/pdf', 'image/png', 'image/jpeg'].includes(f.mime_type)).map(file => <label key={file.id} className="flex min-w-0 items-center gap-2 text-sm"><input type="checkbox" disabled={ai.active} checked={aiSelection.includes(file.id!)} onChange={e => setAiSelection(current => e.target.checked ? [...current, file.id!] : current.filter(id => id !== file.id))} /><span className="break-all">{file.filename}</span></label>)}</div>
        <div className="flex flex-wrap items-center gap-3"><Button disabled={!ai.capabilities?.enabled || !aiSelection.length || ai.active || isSavingReviewDraft} isLoading={ai.busy} onClick={() => void ai.start(aiSelection)}>Проанализировать выбранные</Button>
          {ai.active && <><p role="status" className="text-sm">Анализ выполняется…</p><Button variant="outline" onClick={() => void ai.cancel()}>Отменить анализ</Button></>}
          {ai.run && <span className="text-xs text-gray-500">{ai.run.provider} · {ai.run.model} · обработано {ai.run.documents.filter(d => d.status !== 'queued').length} из {ai.run.documents.length}</span>}
        </div>
        {!!ai.history.length && <div className="mt-3 flex flex-wrap items-center gap-3"><label className="text-sm">Версия предложений<select className="ml-2 rounded-md border p-2" value={ai.run?.id ?? ''} onChange={e => { const run = ai.history.find(r => r.id === e.target.value); if (run) ai.selectRun(run) }}><option value="">Последний запуск</option>{ai.history.map(run => <option key={run.id} value={run.id}>{new Date(run.created_at).toLocaleString('ru-RU')} · {aiStatusLabels[run.status] ?? run.status}</option>)}</select></label>{ai.hasOlder && <Button size="sm" variant="outline" onClick={() => void ai.loadOlder()}>Предыдущие запуски</Button>}</div>}
        {(ai.error || currentJob.report_json.ai_error_code) && <p role="alert" className="mt-3 text-sm text-red-700">{ai.error || aiErrorLabels[currentJob.report_json.ai_error_code ?? ''] || 'Автоматический анализ недоступен.'}</p>}
      </Card>
      {previewFile && <div className="flex flex-wrap gap-2 lg:hidden" aria-label="Сверка документа и полей">
        <Button aria-pressed={mobileTab === 'document'} variant={mobileTab === 'document' ? 'primary' : 'outline'} onClick={() => setMobileTab('document')}>Документ</Button>
        <Button aria-pressed={mobileTab === 'fields'} variant={mobileTab === 'fields' ? 'primary' : 'outline'} onClick={returnToFields}>Поля записи</Button>
      </div>}
      <div className={previewFile ? 'grid min-w-0 gap-6 lg:grid-cols-2' : ''}>
        {previewFile && jobId && <div ref={previewPanel} tabIndex={-1} aria-label="Сверка с исходным документом" className={`${mobileTab === 'document' ? '' : 'hidden lg:block'} min-h-[calc(100svh-6rem)] min-w-0 scroll-mt-24 self-start space-y-3 lg:sticky lg:top-20`}>
          <p className="text-sm text-gray-600">Сверьте поля записи с исходным документом. Просмотр не изменяет введённые данные.</p>
          <DocumentViewer importJobId={jobId} page={previewPage} recordId={jobId} attachmentId={previewFile} onClose={closeSource} onAccessLost={accessLost} />
          <Button className="lg:hidden" variant="outline" onClick={returnToFields}>Вернуться к полям записи</Button>
        </div>}
        <div className={`${previewFile && mobileTab === 'document' ? 'hidden lg:block' : ''} min-w-0 space-y-6`}>
      {decisions.map((decision, patientIndex) => {
        const patientCandidate = patientCandidates.find((item) => item.candidate_id === decision.candidate_id)
        if (!patientCandidate) return null
        const patientOptions = buildPatientOptions(accessiblePatients, patientCandidate)
        if (context.patient && !patientOptions.some(option => option.id === context.patient!.id)) patientOptions.unshift({ id: context.patient.id, label: context.patient.fio, priority: 0 })

        return (
          <Card key={decision.candidate_id} title={patientCandidate.fio ?? 'Пациент не распознан'}>
            {context.patient && <div className="mb-4 rounded-lg border border-primary-100 bg-primary-50 p-3 text-sm">
              <p>Загрузка начата из карточки «{context.patient.fio}». Сверьте имя и дату рождения в документе; при несовпадении выберите другую карточку или распределите документы ниже.</p>
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => updatePatient(patientIndex, { action: 'existing', patient_passport_id: context.patient!.id })}>
                Выбрать {context.patient.fio} для этих документов
              </Button>
            </div>}
            <div id={decision.candidate_id} className="scroll-mt-24" />
            <div className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-3">
                <label className="min-w-0 space-y-1">
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
                    <label className="min-w-0 space-y-1">
                      <span className="text-sm font-medium text-gray-700">ФИО</span>
                      <input
                        className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                        value={decision.fio}
                        onChange={(event) => updatePatient(patientIndex, { fio: event.target.value })}
                      />
                    </label>
                    <label className="min-w-0 space-y-1">
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
                        className="flex w-full items-center gap-3 rounded-sm border border-gray-200 bg-white px-3 py-2 text-left text-sm hover:border-primary-300"
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
                <div className="grid gap-3 rounded-md border border-gray-100 bg-gray-50 p-3 sm:grid-cols-2 sm:items-end">
                  <label className="min-w-0 space-y-1">
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
                  <label className="min-w-0 space-y-1">
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
                  const hasDuplicates = duplicateCandidates.length > 0 || serverDuplicates.includes(group.group_id)
                  const needsDuplicateConfirmation = hasDuplicates && group.action === 'create' && !group.allow_possible_duplicate
                  const isSelected = getSelectedGroupIds(decision.candidate_id).includes(group.group_id)
                  return (
                    <div
                      key={group.group_id}
                      id={`review-group-${group.group_id}`}
                      className="scroll-mt-28 rounded-lg border border-gray-100 p-4"
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <FileText className="h-4 w-4 text-primary-600" />
                          <p className="min-w-0 break-words font-medium text-gray-900">{group.title || sourceGroup?.title || 'Запись'}</p>
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

                      {hasDuplicates && (
                        <div className="mb-3 rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
                          <p className="font-medium">Похожие записи уже есть у пациента</p>
                          {serverDuplicates.includes(group.group_id) && <p className="mt-2">Сервер обнаружил дубль при окончательной проверке. Сравните запись с историей перед подтверждением.</p>}
                          {serverDuplicates.includes(group.group_id) && decision.patient_passport_id && <Link className="font-medium underline" to={`/patients/${decision.patient_passport_id}`} target="_blank" rel="noopener noreferrer">Проверить историю пациента в новой вкладке</Link>}
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
                        <label className="min-w-0 space-y-1">
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
                        <label className="min-w-0 space-y-1">
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
                                      'rounded-sm border px-2 py-1 text-xs transition-colors',
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
                        <label className="min-w-0 space-y-1">
                          <span className="text-xs font-medium text-gray-500">Название</span>
                          <input
                            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                            value={group.title ?? ''}
                            disabled={decision.action === 'skip' || group.action === 'skip'}
                            onChange={(event) => updateGroup(patientIndex, groupIndex, { title: event.target.value })}
                          />
                        </label>
                      </div>

                      <label className="mt-3 block text-sm">Пациент этого документа<select className="mt-1 w-full rounded-md border border-gray-200 p-2" value={decision.candidate_id} disabled={regrouping || isSavingReviewDraft} onChange={e => void moveGroup(group.group_id, e.target.value === '__new' ? null : e.target.value)}><option value={decision.candidate_id}>Текущий пациент</option>{patientCandidates.filter(p => p.candidate_id !== decision.candidate_id).map(p => <option key={p.candidate_id} value={p.candidate_id}>{p.fio ?? 'Другой кандидат пациента'}</option>)}<option value="__new">Отдельный пациент</option></select></label>
                      <label className="mt-3 block text-sm">Клиническое описание<textarea className="mt-1 w-full rounded-md border border-gray-200 p-3" maxLength={10000} value={group.clinical_summary ?? ''} onChange={e => updateGroup(patientIndex, groupIndex, { clinical_summary: e.target.value })} /></label>
                      {ai.run && sourceGroup?.files.map(file => {
                        const document = ai.run?.documents.find(d => d.file_id === file.id)
                        if (!document) return null
                        const needsIdentity = document.result.patient_conflict || document.result.fields?.fio || document.result.fields?.date_of_birth
                        return <React.Fragment key={file.id}><AiSuggestions document={document} runId={ai.run!.id} canApplyIdentity={decision.action === 'create'} onSource={openSource} onApply={(name, value, reference, emptyOnly) => applyAi(patientIndex, groupIndex, name, value, reference, emptyOnly)} />
                          {needsIdentity && !document.result.multiple_patients && <label className="mt-2 flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm"><input type="checkbox" checked={group.patient_identity_confirmed ?? false} onChange={e => updateGroup(patientIndex, groupIndex, { patient_identity_confirmed: e.target.checked })} />Я проверил, что документ относится к выбранному пациенту</label>}</React.Fragment>
                      })}
                      {sourceGroup && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs text-gray-500">
                            Файлов: {sourceGroup.files.length}; DICOM: {sourceGroup.files.filter((file) => file.is_dicom).length}
                          </p>
                          <div className="grid gap-2 md:grid-cols-2">
                            {sourceGroup.files.map((file) => {
                              const hasWarning = warningAffectsFile(warnings, file.path, file.filename)
                              return (
                                <div key={file.path} className="rounded-sm border border-gray-100 bg-gray-50 px-3 py-2 text-xs">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="min-w-0 break-all font-medium text-gray-800">{file.filename}</span>
                                    <span className="shrink-0 text-gray-500">{formatFileSize(file.size_bytes)}</span>
                                  </div>
                                  <div className="mt-1 flex flex-wrap gap-2 text-gray-500">
                                    <span>{file.is_dicom ? 'DICOM' : file.mime_type}</span>
                                    {hasWarning && <span className="text-warning-700">Требует проверки</span>}
                                  </div>
                                  {file.id && <button type="button" aria-label={`Открыть документ ${file.filename}`} className="mt-2 font-medium text-primary-700 underline" onClick={() => openSource(file.id!, 1)}>Открыть документ</button>}
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

        </div>
      </div>
      {warnings.length > 0 && (
        <Card title="Предупреждения" accent="warning">
          <div className="space-y-3 text-sm">
            {warningViews.map((view) => {
              return (
                <div key={view.label} className="space-y-2">
                  <span className={`rounded-sm border px-2 py-0.5 text-xs font-medium ${view.tone}`}>
                    {view.label}: {view.warnings.length}
                  </span>
                  <ul className="space-y-1 text-gray-700">
                    {view.warnings.map((warning, index) => (
                      <li key={`${warning}-${index}`} className="wrap-break-word">{warning}</li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      <div className="flex justify-end">
        <Button type="button" onClick={submit} disabled={isSavingReviewDraft || regrouping} isLoading={isResolving} icon={<Check className="h-4 w-4" />}>
          Подтвердить импорт
        </Button>
      </div>
    </div>
  )

  function openSource(fileId: string, page: number) {
    previewTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setPreviewFile(fileId); setPreviewPage(page); setMobileTab('document')
    if (previewFile === fileId && previewPage === page && mobileTab === 'document') {
      previewPanel.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
      previewPanel.current?.focus({ preventScroll: true })
    }
  }

  function returnToFields() {
    restorePreviewTrigger.current = true
    setMobileTab('fields')
  }

  function closeSource() {
    restorePreviewTrigger.current = true
    setPreviewFile(null)
    setMobileTab('fields')
  }

  function applyAi(patientIndex: number, groupIndex: number, name: AiFieldName, value: string, reference: AppliedAi, emptyOnly = false) {
    const patient = decisions[patientIndex]
    const group = patient.record_groups[groupIndex]
    const existing = name === 'fio' || name === 'date_of_birth' ? patient[name] : group[name]
    if (emptyOnly && existing) return
    if (existing && existing !== value && !window.confirm('Заменить введённое значение предложением AI?')) return
    setDecisions(current => current.map((item, index) => {
      if (index !== patientIndex) return item
      const identity = name === 'fio' || name === 'date_of_birth'
      return { ...item, ...(identity ? { [name]: value } : {}), record_groups: item.record_groups.map((currentGroup, innerIndex) => {
        if (innerIndex !== groupIndex) return identity ? { ...currentGroup, patient_identity_confirmed: false } : currentGroup
        const references = (currentGroup.applied_ai ?? []).map(r => ({ ...r, fields: r.fields.filter(f => f !== name) })).filter(r => r.fields.length)
        return { ...currentGroup, ...(identity ? { patient_identity_confirmed: false } : { [name]: value }),
          applied_ai: [...references, reference], allow_possible_duplicate: false }
      }) }
    }))
  }

  async function moveGroup(groupId: string, targetId: string | null) {
    if (!jobId || !currentJob || isSavingReviewDraft) return
    setRegrouping(true); setFormError('')
    try {
      const response = await api.put<UploadJob>(`/archives/imports/${jobId}/groups`, { version: currentJob.version, group_id: groupId, target_candidate_id: targetId, decisions: decisions.map(toPayload) })
      const restored = restoreDecisions(response.data.report_json.patients ?? [], response.data.review_decisions)
      setDecisions(restored)
      lastSavedSnapshot.current = JSON.stringify(restored.map(toPayload)); lastAttemptedSnapshot.current = lastSavedSnapshot.current
      useUploadStore.setState({ currentJob: response.data })
      setSelectedGroupsByPatient({}); setLastSavedAt(response.data.review_updated_at)
    } catch { setFormError('Не удалось перенести документ. Проверьте, не изменился ли черновик в другой вкладке. Ваши правки сохранены в форме.') }
    finally { setRegrouping(false) }
  }

  function updatePatient(index: number, patch: Partial<PatientDecisionState>) {
    setDecisions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item
      const resetsDuplicateDecision = patch.action !== undefined || patch.patient_passport_id !== undefined || patch.fio !== undefined || patch.date_of_birth !== undefined
      return {
        ...item,
        ...patch,
        record_groups: resetsDuplicateDecision
          ? item.record_groups.map((group) => ({ ...group, allow_possible_duplicate: false, patient_identity_confirmed: false }))
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
  return {
    candidate_id: patient.candidate_id,
    action: 'create',
    patient_passport_id: '',
    fio: patient.fio ?? '',
    date_of_birth: patient.date_of_birth ?? '',
    record_groups: patient.record_groups.map((group) => ({
      group_id: group.group_id,
      action: 'create',
      record_type: group.record_type,
      event_date: group.event_date,
      title: group.title,
      clinical_summary: '',
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
      clinical_summary: group.clinical_summary,
      patient_identity_confirmed: group.patient_identity_confirmed,
      applied_ai: group.applied_ai,
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
