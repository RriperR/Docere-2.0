import axios from 'axios'
import api from '../../api/api'
import { AiFieldName, AppliedAi } from '../../api/importAi'
import RecordGroupEditor from './RecordGroupEditor'
import { useImportAi } from './useImportAi'
import { UploadJob } from '../../stores/uploadStore'
import DocumentViewer from '../../components/records/DocumentViewer'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Check, RotateCcw, UserCheck } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { DateInput } from '../../components/common/DateInput'
import { usePatientsStore } from '../../stores/patientsStore'
import {
  ImportPatientDraft,
  useUploadStore,
} from '../../stores/uploadStore'
import { formatDateForDisplay } from '../../utils/dates'
import { PatientImportContext } from './PatientImportContext'
import { usePatientImportContext } from './usePatientImportContext'
import { groupedWarnings } from '../../utils/importWarnings'
import { buildPatientOptions, toInitialDecision, restoreDecisions, validateDecisions, toPayload, recordTypeLabels, type PatientAction, type PatientDecisionState, type GroupDecisionState, type BulkPatchState } from './reviewState'
import ReviewDocumentList from './ReviewDocumentList'
import ImportAiControls from './ImportAiControls'
import { buildReviewDocuments } from './reviewState'

const UploadReviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
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
  const [previewClosed, setPreviewClosed] = useState(false)
  const previewPanel = useRef<HTMLDivElement>(null)
  const previewTrigger = useRef<HTMLElement | null>(null)
  const restorePreviewTrigger = useRef(false)
  const [mobileTab, setMobileTab] = useState<'fields' | 'document'>('fields')
  const [aiSelection, setAiSelection] = useState<string[]>([])
  const [regrouping, setRegrouping] = useState(false)
  const ai = useImportAi(currentJob)
  const accessLost = React.useCallback(async () => { setPreviewClosed(true); if (jobId) await getJobById(jobId) }, [jobId, getJobById])
  const [serverDuplicates, setServerDuplicates] = useState<string[]>([])
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

  const reviewDocuments = buildReviewDocuments(patientCandidates, decisions, serverDuplicates, ai.run?.documents)
  const requestedGroup = searchParams.get('group')
  const selectedGroupId = reviewDocuments.some(item => item.groupId === requestedGroup)
    ? requestedGroup : reviewDocuments[0]?.groupId ?? null
  const selectedSource = patientCandidates.flatMap(patient => patient.record_groups).find(group => group.group_id === selectedGroupId)
  const requestedFile = searchParams.get('file')
  const selectedFile = selectedSource?.files.find(file => file.id === requestedFile)?.id ?? selectedSource?.files.find(file => file.id)?.id ?? null
  const previewFile = previewClosed ? null : selectedFile
  const rawPage = Number(searchParams.get('page') ?? 1)
  const previewPage = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const editorPanel = useRef<HTMLDivElement>(null)

  useEffect(() => { setPreviewClosed(false) }, [selectedGroupId])

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

  const reviewTotals = {
    ready: reviewDocuments.filter(item => item.status === 'ready').length,
    unresolved: reviewDocuments.filter(item => item.status === 'needs_data').length,
    skipped: reviewDocuments.filter(item => item.status === 'skipped').length,
  }
  const firstReviewIssue = reviewDocuments.find(item => item.status === 'needs_data')
  const selectedRecords = reviewDocuments.filter(item => item.status !== 'skipped').length

  const submit = async () => {
    if (!jobId) return
    const validationError = validateDecisions(decisions, patientCandidates)
    if (validationError) {
      setFormError(validationError)
      if (firstReviewIssue) selectDocument(firstReviewIssue.groupId, true)
      return
    }
    if (decisions.some(patient => patient.action !== 'skip' && patient.record_groups.some(group =>
      serverDuplicates.includes(group.group_id) && group.action === 'create' && !group.allow_possible_duplicate))) {
      setFormError('Решите, импортировать найденный сервером дубль или пропустить запись.')
      if (firstReviewIssue) selectDocument(firstReviewIssue.groupId, true)
      return
    }
    if (firstReviewIssue) {
      setFormError(firstReviewIssue.issue ?? 'Проверьте обязательные поля документа.')
      selectDocument(firstReviewIssue.groupId, true)
      return
    }
    const selectedPatients = decisions.filter(decision => decision.action !== 'skip' && decision.record_groups.some(group => group.action === 'create')).length
    const confirmation = selectedRecords === 0
      ? 'Завершить импорт без создания записей? Все документы будут пропущены.'
      : `Подтвердить импорт: пациентов — ${selectedPatients}, записей — ${selectedRecords}?`
    if (!window.confirm(confirmation)) return
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
        selectDocument(groupId, true)
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
        <h1 className="text-2xl font-bold">Проверка документов</h1>
        <p className="text-gray-500">Выберите документ, сверьте оригинал и поля записи. Правки сохраняются в черновике автоматически.</p>
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
            <span className="font-medium text-success-700">Можно сохранить: {reviewTotals.ready} записей</span>
            <span className={reviewTotals.unresolved > 0 ? 'font-medium text-warning-700' : 'text-gray-500'}>
              Нужны данные: {reviewTotals.unresolved} документов
            </span>
            <span className="text-gray-500">Пропущено: {reviewTotals.skipped} документов</span>
          </div>
          {firstReviewIssue && (
            <button type="button" className="font-medium text-primary-700 hover:underline" onClick={() => selectDocument(firstReviewIssue.groupId, true)}>
              Перейти к следующему вопросу
            </button>
          )}
        </div>
      </Card>

      <ImportAiControls ai={ai} patientCandidates={patientCandidates} selection={aiSelection} onSelectionChange={setAiSelection} saving={isSavingReviewDraft} errorCode={currentJob.report_json.ai_error_code} />
      <section aria-label="Проверка выбранного документа" className="grid min-w-0 gap-4 xl:grid-cols-[15rem_minmax(0,1fr)]">
      <ReviewDocumentList documents={reviewDocuments} selectedId={selectedGroupId} onSelect={selectDocument} disabled={regrouping} />
      <div className="min-w-0 space-y-4">
      <p className="break-words text-sm font-medium text-gray-900">Выбран документ: {selectedSource?.files.find(file => file.id === selectedFile)?.filename ?? selectedSource?.title ?? 'Нет документов'}</p>
      {previewFile && <div className="flex flex-wrap gap-2 lg:hidden" aria-label="Сверка документа и полей">
        <Button aria-pressed={mobileTab === 'document'} variant={mobileTab === 'document' ? 'primary' : 'outline'} onClick={() => setMobileTab('document')}>Документ</Button>
        <Button aria-pressed={mobileTab === 'fields'} variant={mobileTab === 'fields' ? 'primary' : 'outline'} onClick={returnToFields}>Поля записи</Button>
      </div>}
      <div className={previewFile ? 'grid min-w-0 gap-4 lg:grid-cols-2' : ''}>
        {previewFile && jobId && <div ref={previewPanel} tabIndex={-1} aria-label="Сверка с исходным документом" className={`${mobileTab === 'document' ? '' : 'hidden lg:block'} min-w-0 scroll-mt-24 self-start space-y-3 lg:sticky lg:top-20`}>

          <DocumentViewer key={`${jobId}-${selectedGroupId}`} importJobId={jobId} page={previewPage} recordId={jobId} attachmentId={previewFile} importFiles={selectedSource?.files} onAttachmentChange={fileId => openSource(fileId, 1)} onClose={closeSource} onAccessLost={accessLost} />
          <Button className="lg:hidden" variant="outline" onClick={returnToFields}>Вернуться к полям записи</Button>
        </div>}
        <div ref={editorPanel} tabIndex={-1} className={`${previewFile && mobileTab === 'document' ? 'hidden lg:block' : ''} min-w-0 space-y-6 focus:outline-none`}>
      {decisions.map((decision, patientIndex) => {
        const patientCandidate = patientCandidates.find((item) => item.candidate_id === decision.candidate_id)
        if (!patientCandidate || !decision.record_groups.some(group => group.group_id === selectedGroupId)) return null
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
              <p className="text-xs text-gray-500">Выбор карточки и пропуск пациента применяются ко всем его документам: {decision.record_groups.length}.</p>
              <div className="grid gap-4 2xl:grid-cols-2">
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
                <details className="rounded-lg border border-gray-200 p-3">
                  <summary className="cursor-pointer text-sm font-medium">Действия с несколькими документами</summary>
                  <p className="my-2 text-xs text-gray-500">Эти действия относятся ко всем документам этого кандидата пациента. Выбор здесь не меняет включение в импорт.</p>
                  <div className="my-3 space-y-2">{decision.record_groups.map(item => <label key={item.group_id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={getSelectedGroupIds(decision.candidate_id).includes(item.group_id)} onChange={event => toggleGroupSelection(decision.candidate_id, item.group_id, event.target.checked)} />{patientCandidate.record_groups.find(source => source.group_id === item.group_id)?.files[0]?.filename ?? item.title ?? 'Документ'}</label>)}</div>
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
                </details>
                {decision.record_groups.map((group, groupIndex) => group.group_id === selectedGroupId && <RecordGroupEditor
                  key={group.group_id} group={group} sourceGroup={patientCandidate.record_groups.find(source => source.group_id === group.group_id)}
                  decision={decision} patientCandidates={patientCandidates} warnings={warnings} serverDuplicate={serverDuplicates.includes(group.group_id)}
                  status={reviewDocuments.find(item => item.groupId === group.group_id)?.status} regrouping={regrouping || isSavingReviewDraft} aiRun={ai.run}
                  onChange={patch => updateGroup(patientIndex, groupIndex, patch)} onMove={target => moveGroup(group.group_id, target)} onSource={openSource}
                  onApplyAi={(name, value, reference, emptyOnly) => applyAi(patientIndex, groupIndex, name, value, reference, emptyOnly)} />)}
              </div>
            </div>
          </Card>
        )
      })}

        </div>
      </div>
      {selectedGroupId && <div className="flex flex-wrap justify-between gap-3">
        <p className="text-xs text-gray-500">Проверка документа не подтверждает медицинскую запись.</p>
        {reviewDocuments.findIndex(item => item.groupId === selectedGroupId) < reviewDocuments.length - 1 && <Button variant="outline" onClick={() => {
          const index = reviewDocuments.findIndex(item => item.groupId === selectedGroupId)
          selectDocument(reviewDocuments[index + 1].groupId, true)
        }}>Следующий документ</Button>}
      </div>}
      </div>
      </section>
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

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white p-4">
        <p className="text-sm text-gray-600">Записей к сохранению: {selectedRecords}. Пропущено документов: {reviewTotals.skipped}.</p>
        <Button type="button" onClick={submit} disabled={isSavingReviewDraft || regrouping} isLoading={isResolving} icon={<Check className="h-4 w-4" />}>
          {selectedRecords === 0 ? 'Завершить без создания записей' : `Сохранить ${selectedRecords} записей в историю`}
        </Button>
      </div>
    </div>
  )

  function selectDocument(groupId: string, focus = false) {
    const source = patientCandidates.flatMap(patient => patient.record_groups).find(group => group.group_id === groupId)
    if (!source) return
    setSearchParams(current => {
      const next = new URLSearchParams(current)
      next.set('group', groupId)
      const fileId = source.files.find(file => file.id)?.id
      if (fileId) next.set('file', fileId)
      else next.delete('file')
      next.delete('page')
      return next
    })
    setPreviewClosed(false)
    setMobileTab('fields')
    if (focus) window.requestAnimationFrame(() => { editorPanel.current?.scrollIntoView?.({ block: 'start' }); editorPanel.current?.focus({ preventScroll: true }) })
  }

  function openSource(fileId: string, page: number) {
    const source = selectedSource
    if (!source?.files.some(file => file.id === fileId)) return
    previewTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setSearchParams(current => {
      const next = new URLSearchParams(current)
      next.set('group', source.group_id); next.set('file', fileId); next.set('page', String(page))
      return next
    })
    setPreviewClosed(false); setMobileTab('document')
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
    setPreviewClosed(true)
    setMobileTab('fields')
  }

  function applyAi(patientIndex: number, groupIndex: number, name: AiFieldName, value: string, reference: AppliedAi, emptyOnly = false) {
    const patient = decisions[patientIndex]
    const group = patient.record_groups[groupIndex]
    const existing = name === 'fio' || name === 'date_of_birth' ? patient[name] : group[name]
    if (emptyOnly && existing) return
    if (existing && existing !== value && !window.confirm('Заменить введённое значение предложением AI?')) return
    const identity = name === 'fio' || name === 'date_of_birth'
    if (identity || ['record_type', 'event_date', 'title'].includes(name)) {
      invalidateServerDuplicates(identity ? patient.record_groups.map(item => item.group_id) : [group.group_id])
    }
    setDecisions(current => current.map((item, index) => {
      if (index !== patientIndex) return item
      return { ...item, ...(identity ? { [name]: value } : {}), record_groups: item.record_groups.map((currentGroup, innerIndex) => {
        if (innerIndex !== groupIndex) return identity ? { ...currentGroup, patient_identity_confirmed: false, allow_possible_duplicate: false } : currentGroup
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
      invalidateServerDuplicates([groupId])
      lastSavedSnapshot.current = JSON.stringify(restored.map(toPayload)); lastAttemptedSnapshot.current = lastSavedSnapshot.current
      useUploadStore.setState({ currentJob: response.data })
      setSelectedGroupsByPatient({}); setLastSavedAt(response.data.review_updated_at)
    } catch { setFormError('Не удалось перенести документ. Проверьте, не изменился ли черновик в другой вкладке. Ваши правки сохранены в форме.') }
    finally { setRegrouping(false) }
  }

  function changesDuplicateKey(patch: Partial<GroupDecisionState>) {
    return patch.record_type !== undefined || patch.event_date !== undefined || patch.title !== undefined
  }

  // Серверный результат относится к прежним полям и пациенту. После правки сервер проверит запись заново.
  function invalidateServerDuplicates(groupIds: string[]) {
    if (groupIds.length === 0) return
    setServerDuplicates(current => current.filter(groupId => !groupIds.includes(groupId)))
  }

  function updatePatient(index: number, patch: Partial<PatientDecisionState>) {
    const resetsDuplicateDecision = patch.action !== undefined || patch.patient_passport_id !== undefined || patch.fio !== undefined || patch.date_of_birth !== undefined
    if (resetsDuplicateDecision) invalidateServerDuplicates(decisions[index].record_groups.map(group => group.group_id))
    setDecisions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item
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
    if (changesDuplicateKey(patch)) invalidateServerDuplicates([decisions[patientIndex].record_groups[groupIndex].group_id])
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
                    changesDuplicateKey(patch)
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
    if (changesDuplicateKey(patch)) invalidateServerDuplicates(decisions[patientIndex].record_groups.map(group => group.group_id))
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
    if (changesDuplicateKey(patch)) invalidateServerDuplicates(selectedGroupIds)
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
                    changesDuplicateKey(patch)
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
    invalidateServerDuplicates(decisions[patientIndex].record_groups.filter(group => !group.event_date &&
      patient.record_groups.some(source => source.group_id === group.group_id && source.event_date_candidates[0]))
      .map(group => group.group_id))
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
    setServerDuplicates([])
    setSelectedGroupsByPatient({})
    setBulkPatchByPatient({})
    setFormError('')
  }
}

export default UploadReviewPage
