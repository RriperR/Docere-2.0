import React, { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  Building2,
  Calendar,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  MessageSquare,
  Paperclip,
  Search,
  Send,
  Share2,
  Stethoscope,
  User,
  X,
} from 'lucide-react'
import { format } from 'date-fns'

import { AddRecordModal } from '../../components/AddRecordModal'
import { Button } from '../../components/common/Button'
import { DateInput } from '../../components/common/DateInput'
import { useAuthStore } from '../../stores/authStore'
import { PatientRecordSummary, usePatientsStore } from '../../stores/patientsStore'
import { CreateShareResult, ShareRecipient, useShareRequestsStore } from '../../stores/shareRequestsStore'
import { attachmentSizeError } from '../../utils/files'

type ApiError = {
  response?: { data?: { detail?: string } }
  message?: string
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) return fallback
  const e = error as ApiError
  return e.response?.data?.detail ?? e.message ?? fallback
}

const accessContextLabel = (ctx: string) =>
  ctx === 'shared' ? 'Sharing' : ctx === 'created' ? 'Локальная карточка' : 'Моя карточка'

const accessContextClasses = (ctx: string) =>
  ctx === 'shared'
    ? 'bg-warning-50 text-warning-700 border-warning-200'
    : ctx === 'created'
      ? 'bg-accent-50 text-accent-700 border-accent-200'
      : 'bg-success-50 text-success-700 border-success-200'

const typeLabel: Record<string, string> = {
  consultation_result: 'Консультация',
  exam_result: 'Обследование',
  lab_result: 'Лаборатория',
  other: 'Другое',
}

const typeColors: Record<string, string> = {
  consultation_result: 'bg-accent-100 text-accent-700',
  exam_result: 'bg-secondary-100 text-secondary-700',
  lab_result: 'bg-warning-100 text-warning-700',
  other: 'bg-gray-100 text-gray-600',
}

type TimelineGroup = {
  label: string
  records: PatientRecordSummary[]
}

function getInitials(fio: string): string {
  const parts = fio.trim().split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return fio[0]?.toUpperCase() ?? '?'
}

const commentRoleLabel: Record<string, string> = {
  doctor: 'Врач',
  admin: 'Администратор',
  patient: 'Пациент',
}

const PatientDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuthStore()
  const {
    currentPatient,
    patientRecords,
    activeRecord,
    isLoading,
    error,
    fetchPatientById,
    fetchPatientRecords,
    fetchRecordDetail,
    addRecordComment,
    uploadCommentAttachment,
    uploadRecordAttachment,
    downloadAttachment,
    clearActiveRecord,
  } = usePatientsStore()
  const createShareRequest = useShareRequestsStore((s) => s.createShareRequest)
  const recipients = useShareRequestsStore((s) => s.recipients)
  const searchRecipients = useShareRequestsStore((s) => s.searchRecipients)
  const clearRecipients = useShareRequestsStore((s) => s.clearRecipients)

  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
  const [selectedShareRecordIds, setSelectedShareRecordIds] = useState<string[]>([])
  const [isShareModalOpen, setIsShareModalOpen] = useState(false)
  const [shareEmail, setShareEmail] = useState('')
  const [shareMessage, setShareMessage] = useState('')
  const [shareExpiresAt, setShareExpiresAt] = useState('')
  const [shareResult, setShareResult] = useState<CreateShareResult | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [shareSubmitting, setShareSubmitting] = useState(false)
  const [commentBody, setCommentBody] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [commentSubmitting, setCommentSubmitting] = useState(false)
  const [uploadingCommentId, setUploadingCommentId] = useState<string | null>(null)
  const [uploadingRecordId, setUploadingRecordId] = useState<string | null>(null)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [recordSearch, setRecordSearch] = useState('')
  const [recordTypeFilter, setRecordTypeFilter] = useState('all')
  const [recordStatusFilter, setRecordStatusFilter] = useState('all')
  const [recordDateFrom, setRecordDateFrom] = useState('')
  const [recordDateTo, setRecordDateTo] = useState('')

  useEffect(() => {
    if (id) {
      void fetchPatientById(id)
      void fetchPatientRecords(id)
      clearActiveRecord()
      setSelectedRecordId(null)
      setSelectedShareRecordIds([])
    }
  }, [id, fetchPatientById, fetchPatientRecords, clearActiveRecord])

  useEffect(() => {
    if (selectedRecordId) void fetchRecordDetail(selectedRecordId)
  }, [selectedRecordId, fetchRecordDetail])

  useEffect(() => {
    if (!isShareModalOpen) return
    const timer = window.setTimeout(() => {
      void searchRecipients(shareEmail)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [isShareModalOpen, shareEmail, searchRecipients])

  const canComment = user?.role === 'doctor' || user?.role === 'admin'

  const filteredRecords = useMemo(() => {
    const query = recordSearch.trim().toLowerCase()
    const fromTime = recordDateFrom ? new Date(recordDateFrom).getTime() : null
    const toTime = recordDateTo ? new Date(recordDateTo).getTime() : null

    return patientRecords
      .filter((record) => {
        const recordTime = new Date(record.eventDate).getTime()
        const matchesQuery = !query || [
          record.title,
          record.clinicalSummary,
          record.appointmentLocation,
          record.creatorFio,
          record.practitioner?.full_name,
          record.practitioner?.organization,
          typeLabel[record.recordType],
        ].some((value) => value?.toLowerCase().includes(query))

        return (
          matchesQuery &&
          (recordTypeFilter === 'all' || record.recordType === recordTypeFilter) &&
          (recordStatusFilter === 'all' || record.status === recordStatusFilter) &&
          (fromTime === null || recordTime >= fromTime) &&
          (toTime === null || recordTime <= toTime)
        )
      })
      .sort((left, right) => new Date(right.eventDate).getTime() - new Date(left.eventDate).getTime())
  }, [patientRecords, recordDateFrom, recordDateTo, recordSearch, recordStatusFilter, recordTypeFilter])

  const timelineGroups = useMemo<TimelineGroup[]>(() => {
    const groups = new Map<string, PatientRecordSummary[]>()
    filteredRecords.forEach((record) => {
      const label = new Date(record.eventDate).toLocaleDateString('ru-RU', {
        month: 'long',
        year: 'numeric',
      })
      groups.set(label, [...(groups.get(label) ?? []), record])
    })
    return Array.from(groups.entries()).map(([label, records]) => ({ label, records }))
  }, [filteredRecords])

  const unconfirmedRecordsCount = patientRecords.filter((record) => record.status === 'unconfirmed').length
  const recordsWithAttachmentsCount = patientRecords.filter((record) => record.attachmentsCount > 0).length

  const handleOpenRecord = (record: PatientRecordSummary) => {
    setSelectedRecordId((c) => (c === record.id ? null : record.id))
    setCommentBody('')
    setCommentError(null)
  }

  const handleAddComment = async () => {
    if (!selectedRecordId || !commentBody.trim()) return
    setCommentSubmitting(true)
    setCommentError(null)
    try {
      await addRecordComment(selectedRecordId, commentBody.trim())
      await fetchRecordDetail(selectedRecordId)
      setCommentBody('')
    } catch (e: unknown) {
      setCommentError(getErrorMessage(e, 'Не удалось добавить комментарий'))
    } finally {
      setCommentSubmitting(false)
    }
  }

  const handleUploadCommentFile = async (
    recordId: string,
    commentId: string,
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const sizeError = attachmentSizeError(file)
    if (sizeError) {
      setCommentError(sizeError)
      return
    }
    setUploadingCommentId(commentId)
    setCommentError(null)
    try {
      await uploadCommentAttachment(recordId, commentId, file)
    } catch (e: unknown) {
      setCommentError(getErrorMessage(e, 'Не удалось загрузить файл'))
    } finally {
      setUploadingCommentId(null)
    }
  }

  const handleUploadRecordFile = async (recordId: string, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const sizeError = attachmentSizeError(file)
    if (sizeError) {
      setAttachmentError(sizeError)
      return
    }
    setUploadingRecordId(recordId)
    setAttachmentError(null)
    try {
      await uploadRecordAttachment(recordId, file)
    } catch (e: unknown) {
      setAttachmentError(getErrorMessage(e, 'Не удалось загрузить файл'))
    } finally {
      setUploadingRecordId(null)
    }
  }

  const handleShareSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setShareError(null)
    setShareResult(null)
    if (!shareEmail.trim()) { setShareError('Укажите email получателя'); return }
    if (selectedShareRecordIds.length === 0) { setShareError('Выберите хотя бы одну запись'); return }
    setShareSubmitting(true)
    try {
      const result = await createShareRequest({
        to_user_email: shareEmail.trim(),
        record_ids: selectedShareRecordIds,
        message: shareMessage.trim() || undefined,
        expires_at: shareExpiresAt || null,
      })
      setShareResult(result)
      if (result.request) setSelectedShareRecordIds([])
    } catch (e: unknown) {
      setShareError(getErrorMessage(e, 'Не удалось отправить запрос'))
    } finally {
      setShareSubmitting(false)
    }
  }

  const closeShareModal = () => {
    setIsShareModalOpen(false)
    setShareEmail('')
    setShareMessage('')
    setShareExpiresAt('')
    setShareResult(null)
    setShareError(null)
    clearRecipients()
  }

  if (!id) return null

  if (isLoading && !currentPatient) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 w-40 rounded bg-gray-200" />
        <div className="h-10 w-80 rounded bg-gray-200" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-32 rounded-xl bg-gray-200" />)}
        </div>
      </div>
    )
  }

  if (error) return <p className="mt-8 text-center text-error-600">{error}</p>
  if (!currentPatient) return null

  const patientInitials = getInitials(currentPatient.fio)
  const selectedShareRecords = patientRecords.filter((record) => selectedShareRecordIds.includes(record.id))

  return (
    <div className="space-y-6">
      {/* Breadcrumb + Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Link
          to="/patients"
          className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-primary-600"
        >
          <ArrowLeft className="h-4 w-4" />
          Назад к списку пациентов
        </Link>

        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-600 text-xl font-bold text-white">
              {patientInitials}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{currentPatient.fio}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${accessContextClasses(currentPatient.accessContext)}`}>
                  {accessContextLabel(currentPatient.accessContext)}
                </span>
                <span className="text-xs text-gray-400">ID: {currentPatient.id}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              icon={<Share2 className="h-4 w-4" />}
              disabled={selectedShareRecordIds.length === 0}
              onClick={() => setIsShareModalOpen(true)}
              size="sm"
            >
              Поделиться ({selectedShareRecordIds.length})
            </Button>
            <Button onClick={() => setShowAddModal(true)} size="sm">
              + Добавить запись
            </Button>
          </div>
        </div>
      </motion.div>

      {currentPatient.accessContext === 'shared' && (
        <div className="rounded-xl border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          Эта карточка доступна вам по sharing. Она может относиться к другому пациенту.
        </div>
      )}

      {/* Patient info cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
          <div className="mb-3 flex items-center gap-2 text-primary-600">
            <User className="h-4 w-4" />
            <span className="text-sm font-semibold">Пациент</span>
          </div>
          <div className="space-y-2.5 text-sm">
            {[
              { label: 'ФИО', value: currentPatient.fio },
              { label: 'Тип доступа', value: accessContextLabel(currentPatient.accessContext) },
              { label: 'Дата рождения', value: currentPatient.birthday ? format(new Date(currentPatient.birthday), 'dd.MM.yyyy') : 'Не указана' },
              { label: 'Email', value: currentPatient.email || 'Не указан' },
              { label: 'Телефон', value: currentPatient.phone || 'Не указан' },
            ].map((row) => (
              <div key={row.label} className="flex justify-between gap-2">
                <span className="text-gray-400">{row.label}</span>
                <span className="text-right font-medium text-gray-900">{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
          <div className="mb-3 flex items-center gap-2 text-primary-600">
            <FileText className="h-4 w-4" />
            <span className="text-sm font-semibold">Сводка</span>
          </div>
          <div className="space-y-3">
            <div className="rounded-lg bg-primary-50 p-3 text-center">
              <p className="text-3xl font-bold text-primary-600">{patientRecords.length}</p>
              <p className="mt-0.5 text-xs text-gray-500">Всего записей</p>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Последняя запись</span>
              <span className="font-medium">{currentPatient.lastVisit ? format(new Date(currentPatient.lastVisit), 'dd.MM.yyyy') : '—'}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Неподтверждённые</span>
              <span className="font-medium">{unconfirmedRecordsCount}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">С вложениями</span>
              <span className="font-medium">{recordsWithAttachmentsCount}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Статус</span>
              <span className="font-medium capitalize">{currentPatient.status}</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
          <div className="mb-3 flex items-center gap-2 text-primary-600">
            <Share2 className="h-4 w-4" />
            <span className="text-sm font-semibold">Sharing</span>
          </div>
          <p className="text-sm text-gray-500">
            Отметьте нужные записи галочкой и нажмите «Поделиться» — получатель получит доступ
            после принятия запроса.
          </p>
        </div>
      </div>

      {/* Records */}
      <div>
        <div className="mb-3 flex flex-col gap-3 px-1 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">Медицинские записи</h2>
            <p className="mt-0.5 text-xs text-gray-400">
              Нажмите на запись, чтобы раскрыть детали. История сгруппирована по дате события.
            </p>
          </div>
          {patientRecords.length > 0 && (
            <span className="text-xs text-gray-400">{filteredRecords.length} из {patientRecords.length}</span>
          )}
        </div>

        {patientRecords.length > 0 && (
          <div className="mb-4 grid gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-card lg:grid-cols-[minmax(220px,1.3fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)]">
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-500">Поиск</span>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={recordSearch}
                  onChange={(event) => setRecordSearch(event.target.value)}
                  className="w-full rounded-md border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-100"
                  placeholder="Название, врач, место..."
                />
              </div>
            </label>
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-500">Тип</span>
              <select
                value={recordTypeFilter}
                onChange={(event) => setRecordTypeFilter(event.target.value)}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-100"
              >
                <option value="all">Все типы</option>
                {Object.entries(typeLabel).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-500">Статус</span>
              <select
                value={recordStatusFilter}
                onChange={(event) => setRecordStatusFilter(event.target.value)}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-100"
              >
                <option value="all">Все статусы</option>
                <option value="confirmed">Подтверждённые</option>
                <option value="unconfirmed">Неподтверждённые</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-500">С даты</span>
              <DateInput
                value={recordDateFrom}
                onChange={(value) => setRecordDateFrom(value ?? '')}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-500">По дату</span>
              <DateInput
                value={recordDateTo}
                onChange={(value) => setRecordDateTo(value ?? '')}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
              />
            </label>
          </div>
        )}

        {patientRecords.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-gray-100 bg-white py-14 text-center shadow-card">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <FileText className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-gray-900">Записей пока нет</p>
            <p className="mt-1 text-xs text-gray-500">Нажмите «Добавить запись» чтобы создать первую</p>
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-gray-100 bg-white py-14 text-center shadow-card">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <Search className="h-6 w-6 text-gray-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-gray-900">Ничего не найдено</p>
            <p className="mt-1 text-xs text-gray-500">Измените фильтры или период истории</p>
          </div>
        ) : (
          <div className="space-y-6">
            {timelineGroups.map((group) => (
              <section key={group.label} className="space-y-3">
                <div className="flex items-center gap-3 px-1">
                  <h3 className="text-sm font-semibold capitalize text-gray-700">{group.label}</h3>
                  <span className="h-px flex-1 bg-gray-100" />
                  <span className="text-xs text-gray-400">{group.records.length}</span>
                </div>
                {group.records.map((record) => {
              const isOpen = selectedRecordId === record.id
              const detail = isOpen && activeRecord?.id === record.id ? activeRecord : null
              const isSelectedForShare = selectedShareRecordIds.includes(record.id)

              return (
                <div
                  key={record.id}
                  className={`relative overflow-hidden rounded-xl border bg-white transition-all ${
                    isSelectedForShare
                      ? 'border-primary-300 ring-1 ring-primary-200'
                      : isOpen
                        ? 'border-primary-200 shadow-card'
                        : 'border-gray-200 hover:border-gray-300 hover:shadow-card'
                  }`}
                >
                  <label
                    className="absolute left-4 top-5 z-10 flex cursor-pointer items-center"
                    title="Выбрать запись для sharing"
                  >
                    <input
                      type="checkbox"
                      checked={isSelectedForShare}
                      onChange={() => setSelectedShareRecordIds((c) =>
                        c.includes(record.id) ? c.filter((x) => x !== record.id) : [...c, record.id]
                      )}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </label>

                  <button
                    type="button"
                    onClick={() => handleOpenRecord(record)}
                    className="flex w-full items-start justify-between gap-4 py-4 pl-12 pr-6 text-left"
                  >
                    <div className="flex flex-col gap-2 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${typeColors[record.recordType] ?? 'bg-gray-100 text-gray-600'}`}>
                          {typeLabel[record.recordType] ?? record.recordType}
                        </span>
                        <span className="flex items-center gap-1 text-xs text-gray-400">
                          <Calendar className="h-3 w-3" />
                          {format(new Date(record.eventDate), 'dd.MM.yyyy')}
                        </span>
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs capitalize text-gray-600">
                          {record.status}
                        </span>
                        {record.confirmedAt && (
                          <span className="rounded-full bg-success-50 px-2 py-0.5 text-xs text-success-700">
                            подтверждено {format(new Date(record.confirmedAt), 'dd.MM.yyyy')}
                          </span>
                        )}
                      </div>
                      <p className="text-base font-semibold text-gray-900">
                        {record.title || 'Медицинская запись'}
                      </p>
                      {record.clinicalSummary && (
                        <p className="text-sm text-gray-500 line-clamp-2">{record.clinicalSummary}</p>
                      )}
                      <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                        {record.appointmentLocation && (
                          <span className="flex items-center gap-1">
                            <Building2 className="h-3.5 w-3.5" />
                            {record.appointmentLocation}
                          </span>
                        )}
                        {record.practitioner?.full_name && (
                          <span className="flex items-center gap-1">
                            <Stethoscope className="h-3.5 w-3.5" />
                            {record.practitioner.full_name}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <User className="h-3.5 w-3.5" />
                          {record.creatorFio}
                        </span>
                        <span>{format(new Date(record.createdAt), 'dd.MM.yyyy HH:mm')}</span>
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3.5 w-3.5" />
                          {record.commentsCount}
                        </span>
                        <span className="flex items-center gap-1">
                          <Paperclip className="h-3.5 w-3.5" />
                          {record.attachmentsCount}
                        </span>
                      </div>
                    </div>
                    <span className="shrink-0 text-gray-400">
                      {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                    </span>
                  </button>

                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="border-t border-primary-100 bg-white px-6 py-5">
                          {detail ? (
                            <div className="space-y-6">
                              <ImportProvenancePanel payloadJson={detail.payloadJson} />

                              {/* Вложения — действие наверху, чтобы не листать до конца */}
                              <div>
                                <div className="mb-3 flex items-center justify-between">
                                  <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-gray-400">
                                    <Paperclip className="h-3.5 w-3.5" />
                                    Вложения ({detail.attachments.length})
                                  </h4>
                                  <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-primary-200 bg-primary-50 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-100">
                                    <Paperclip className="h-3.5 w-3.5" />
                                    {uploadingRecordId === detail.id ? 'Загрузка…' : 'Прикрепить файл'}
                                    <input
                                      type="file"
                                      className="hidden"
                                      disabled={uploadingRecordId === detail.id}
                                      onChange={(e) => void handleUploadRecordFile(detail.id, e)}
                                    />
                                  </label>
                                </div>
                                {attachmentError && (
                                  <p className="mb-2 text-xs text-error-600">{attachmentError}</p>
                                )}
                                {detail.attachments.length === 0 ? (
                                  <p className="rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm text-gray-400">
                                    Вложений пока нет. Нажмите «Прикрепить файл», чтобы добавить.
                                  </p>
                                ) : (
                                  <div className="space-y-2">
                                    {detail.attachments.map((a) => (
                                      <button
                                        key={a.id}
                                        type="button"
                                        onClick={() => void downloadAttachment(detail.id, a.id, a.filename ?? 'file')}
                                        className="flex w-full items-center gap-3 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 text-left hover:border-primary-300 hover:bg-primary-50"
                                      >
                                        <Paperclip className="h-4 w-4 shrink-0 text-gray-400" />
                                        <div className="min-w-0 flex-1">
                                          <p className="truncate text-sm font-medium text-gray-900">{a.filename ?? 'Файл'}</p>
                                          <p className="text-xs text-gray-400">
                                            {a.uploaded_by_fio} · {format(new Date(a.uploaded_at), 'dd.MM.yyyy HH:mm')} ·{' '}
                                            {Math.ceil(a.size_bytes / 1024)} КБ
                                          </p>
                                        </div>
                                        <Download className="h-4 w-4 shrink-0 text-primary-600" />
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>

                              {/* Комментарии */}
                              <div>
                                <h4 className="mb-3 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-gray-400">
                                  <MessageSquare className="h-3.5 w-3.5" />
                                  Комментарии ({detail.comments.length})
                                </h4>
                                {detail.comments.length === 0 ? (
                                  <p className="text-sm text-gray-400">Комментариев пока нет.</p>
                                ) : (
                                  <div className="space-y-3">
                                    {detail.comments.map((comment) => (
                                      <div key={comment.id} className="rounded-xl border border-gray-100 bg-gray-50 p-4">
                                        <div className="mb-1.5 flex items-center gap-2">
                                          <span className="text-sm font-semibold text-gray-900">{comment.author_fio}</span>
                                          <span className="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary-600">
                                            {commentRoleLabel[comment.author_role] ?? comment.author_role}
                                          </span>
                                        </div>
                                        <p className="text-sm text-gray-800">{comment.body}</p>
                                        {comment.attachments.length > 0 && (
                                          <div className="mt-2 space-y-1.5">
                                            {comment.attachments.map((att) => (
                                              <button
                                                key={att.id}
                                                type="button"
                                                onClick={() =>
                                                  void downloadAttachment(detail.id, att.id, att.filename ?? 'file')
                                                }
                                                className="flex w-full items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-xs text-gray-700 hover:border-primary-300 hover:bg-primary-50"
                                              >
                                                <Paperclip className="h-3.5 w-3.5 shrink-0 text-gray-400" />
                                                <span className="flex-1 truncate">{att.filename ?? 'Файл'}</span>
                                                <span className="text-gray-400">{Math.ceil(att.size_bytes / 1024)} КБ</span>
                                                <Download className="h-3.5 w-3.5 shrink-0 text-primary-600" />
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                        <div className="mt-1.5 flex items-center justify-between">
                                          <p className="text-xs text-gray-400">
                                            {format(new Date(comment.created_at), 'dd.MM.yyyy HH:mm')}
                                          </p>
                                          {canComment && (
                                            <label className="flex cursor-pointer items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700">
                                              <Paperclip className="h-3.5 w-3.5" />
                                              {uploadingCommentId === comment.id ? 'Загрузка…' : 'Прикрепить файл'}
                                              <input
                                                type="file"
                                                className="hidden"
                                                disabled={uploadingCommentId === comment.id}
                                                onChange={(e) => void handleUploadCommentFile(detail.id, comment.id, e)}
                                              />
                                            </label>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {canComment && (
                                  <div className="mt-4 space-y-2">
                                    <div className="flex gap-2">
                                      <textarea
                                        value={commentBody}
                                        onChange={(e) => setCommentBody(e.target.value)}
                                        rows={2}
                                        className="flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm placeholder-gray-400 focus:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-200"
                                        placeholder="Добавить комментарий к записи..."
                                      />
                                      <button
                                        type="button"
                                        onClick={handleAddComment}
                                        disabled={commentSubmitting || !commentBody.trim()}
                                        className="flex h-10 w-10 shrink-0 items-center justify-center self-end rounded-xl bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-40"
                                      >
                                        <Send className="h-4 w-4" />
                                      </button>
                                    </div>
                                    {commentError && <p className="text-xs text-error-600">{commentError}</p>}
                                  </div>
                                )}
                              </div>

                              {/* Данные записи — сворачиваемый JSON внизу, как тех. детали */}
                              <details className="group rounded-xl border border-gray-100 bg-gray-50">
                                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-gray-400 [&::-webkit-details-marker]:hidden">
                                  <span>Данные записи (JSON)</span>
                                  <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                                </summary>
                                <pre className="overflow-x-auto border-t border-gray-100 p-4 text-xs text-gray-700">
                                  {JSON.stringify(detail.payloadJson, null, 2)}
                                </pre>
                              </details>
                            </div>
                          ) : (
                            <div className="space-y-2 animate-pulse">
                              <div className="h-4 w-40 rounded bg-gray-200" />
                              <div className="h-20 w-full rounded-xl bg-gray-200" />
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
                })}
              </section>
            ))}
          </div>
        )}
      </div>

      {showAddModal && (
        <AddRecordModal
          patientId={id!}
          onClose={() => {
            setShowAddModal(false)
            void fetchPatientRecords(id!)
          }}
        />
      )}

      {isShareModalOpen && (
        <ShareRecordsModal
          selectedCount={selectedShareRecordIds.length}
          selectedRecords={selectedShareRecords}
          email={shareEmail}
          message={shareMessage}
          expiresAt={shareExpiresAt}
          result={shareResult}
          error={shareError}
          isSubmitting={shareSubmitting}
          recipients={recipients}
          onEmailChange={setShareEmail}
          onMessageChange={setShareMessage}
          onExpiresAtChange={setShareExpiresAt}
          onSelectRecipient={setShareEmail}
          onSubmit={handleShareSubmit}
          onClose={closeShareModal}
        />
      )}
    </div>
  )
}

function ShareRecordsModal({
  selectedCount, selectedRecords, email, message, expiresAt, result, error, isSubmitting, recipients,
  onEmailChange, onMessageChange, onExpiresAtChange, onSelectRecipient, onSubmit, onClose,
}: {
  selectedCount: number
  selectedRecords: PatientRecordSummary[]
  email: string
  message: string
  expiresAt: string
  result: CreateShareResult | null
  error: string | null
  isSubmitting: boolean
  recipients: ShareRecipient[]
  onEmailChange: (v: string) => void
  onMessageChange: (v: string) => void
  onExpiresAtChange: (v: string) => void
  onSelectRecipient: (email: string) => void
  onSubmit: (e: FormEvent) => void
  onClose: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/60 p-4 backdrop-blur-sm"
    >
      <motion.form
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        onSubmit={onSubmit}
        className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Поделиться записями</h2>
            <p className="mt-0.5 text-sm text-gray-500">Выбрано: {selectedCount} запис{selectedCount === 1 ? 'ь' : 'ей'}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && <div className="mb-4 rounded-xl bg-error-50 px-4 py-3 text-sm text-error-700">{error}</div>}
        {result && (
          <div className="mb-4 rounded-xl bg-success-50 px-4 py-3 text-sm text-success-800">
            {result.request
              ? `Sharing-запрос создан: отправлено ${result.request.shares.length} записей.`
              : 'Новые записи не добавлены: у получателя уже есть доступ или активный запрос.'}
            {result.skipped_record_ids.length > 0 && (
              <p className="mt-1 text-xs">Пропущено: {result.skipped_record_ids.length}</p>
            )}
            {result.request && (
              <Link to="/share-requests" className="mt-2 inline-flex text-xs font-medium text-success-900 underline">
                Открыть исходящие
              </Link>
            )}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Выбранные записи</p>
            <div className="max-h-40 space-y-2 overflow-y-auto rounded-xl border border-gray-100 bg-gray-50 p-2">
              {selectedRecords.map((record) => (
                <div key={record.id} className="rounded-lg bg-white px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${typeColors[record.recordType] ?? 'bg-gray-100 text-gray-600'}`}>
                      {typeLabel[record.recordType] ?? record.recordType}
                    </span>
                    <span className="text-xs text-gray-500">{format(new Date(record.eventDate), 'dd.MM.yyyy')}</span>
                  </div>
                  <p className="mt-1 font-medium text-gray-900">{record.title || 'Медицинская запись'}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Email получателя</label>
            <input
              type="text"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
              placeholder="email или ФИО получателя"
            />
            {recipients.length > 0 && (
              <div className="mt-2 max-h-44 overflow-y-auto rounded-xl border border-gray-200 bg-white">
                {recipients.map((recipient) => (
	                  <button
	                    key={recipient.id}
	                    type="button"
	                    onClick={() => onSelectRecipient(recipient.email)}
	                    className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-primary-50 ${
	                      email === recipient.email ? 'bg-primary-50' : ''
	                    }`}
	                  >
                    <span>
                      <span className="block font-medium text-gray-900">{recipient.fio}</span>
                      <span className="text-xs text-gray-500">{recipient.email}</span>
                    </span>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{recipient.role}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Сообщение (необязательно)</label>
            <textarea
              value={message}
              onChange={(e) => onMessageChange(e.target.value)}
              rows={3}
              className="mt-1.5 w-full resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
              placeholder="Контекст для получателя..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Срок доступа</label>
            <DateInput
              value={expiresAt}
              onChange={(value) => onExpiresAtChange(value ?? '')}
              className="mt-1.5 w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
            />
            <p className="mt-1 text-xs text-gray-400">Пусто — доступ без срока. В выбранный день доступ действует до конца дня.</p>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Отмена</Button>
          <Button type="submit" isLoading={isSubmitting}>Отправить запрос</Button>
        </div>
      </motion.form>
    </motion.div>
  )
}

function ImportProvenancePanel({ payloadJson }: { payloadJson: Record<string, unknown> }) {
  const provenance = getImportProvenance(payloadJson)
  if (!provenance) return null

  return (
    <div className="rounded-xl border border-primary-100 bg-primary-50 px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wider text-primary-600">Источник записи</p>
      <div className="mt-2 grid gap-2 text-sm text-primary-900 md:grid-cols-3">
        <div>
          <span className="block text-xs text-primary-600">Архив</span>
          <span className="font-medium">{provenance.sourceArchive || 'archive.zip'}</span>
        </div>
        <div>
          <span className="block text-xs text-primary-600">Файлов</span>
          <span className="font-medium">{provenance.filesCount}</span>
        </div>
        <div>
          <span className="block text-xs text-primary-600">Import job</span>
          <span className="font-mono text-xs">{provenance.importJobId}</span>
        </div>
      </div>
    </div>
  )
}

function getImportProvenance(payloadJson: Record<string, unknown>) {
  const raw = payloadJson.import_provenance
  if (!raw || typeof raw !== 'object') return null
  const provenance = raw as Record<string, unknown>
  const files = Array.isArray(provenance.files) ? provenance.files : []
  return {
    sourceArchive: typeof provenance.source_archive === 'string' ? provenance.source_archive : null,
    importJobId: typeof provenance.import_job_id === 'string' ? provenance.import_job_id : '—',
    filesCount: files.length,
  }
}

export default PatientDetailsPage
