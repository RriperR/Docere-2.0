import React, { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  Building2,
  Calendar,
  FileText,
  MessageSquare,
  Share2,
  Stethoscope,
} from 'lucide-react'
import { format } from 'date-fns'

import { AddRecordModal } from '../../components/AddRecordModal'
import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { useAuthStore } from '../../stores/authStore'
import { PatientRecordSummary, usePatientsStore } from '../../stores/patientsStore'
import { CreateShareResult, useShareRequestsStore } from '../../stores/shareRequestsStore'

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
  message?: string
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error !== 'object' || error === null) {
    return fallback
  }

  const apiError = error as ApiError
  return apiError.response?.data?.detail || apiError.message || fallback
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
    clearActiveRecord,
  } = usePatientsStore()
  const createShareRequest = useShareRequestsStore((state) => state.createShareRequest)

  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
  const [selectedShareRecordIds, setSelectedShareRecordIds] = useState<string[]>([])
  const [isShareModalOpen, setIsShareModalOpen] = useState(false)
  const [shareEmail, setShareEmail] = useState('')
  const [shareMessage, setShareMessage] = useState('')
  const [shareResult, setShareResult] = useState<CreateShareResult | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [shareSubmitting, setShareSubmitting] = useState(false)
  const [commentBody, setCommentBody] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [commentSubmitting, setCommentSubmitting] = useState(false)

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
    if (selectedRecordId) {
      void fetchRecordDetail(selectedRecordId)
    }
  }, [selectedRecordId, fetchRecordDetail])

  const canComment = user?.role === 'doctor' || user?.role === 'admin'

  const handleOpenRecord = (record: PatientRecordSummary) => {
    setSelectedRecordId((current) => (current === record.id ? null : record.id))
    setCommentBody('')
    setCommentError(null)
  }

  const handleToggleShareRecord = (recordId: string) => {
    setSelectedShareRecordIds((current) =>
      current.includes(recordId)
        ? current.filter((selectedRecordId) => selectedRecordId !== recordId)
        : [...current, recordId],
    )
  }

  const handleAddComment = async () => {
    if (!selectedRecordId || !commentBody.trim()) {
      return
    }

    setCommentSubmitting(true)
    setCommentError(null)
    try {
      await addRecordComment(selectedRecordId, commentBody.trim())
      await fetchRecordDetail(selectedRecordId)
      setCommentBody('')
    } catch (submitError: unknown) {
      setCommentError(getErrorMessage(submitError, 'Не удалось добавить комментарий'))
    } finally {
      setCommentSubmitting(false)
    }
  }

  const handleShareSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setShareError(null)
    setShareResult(null)

    if (!shareEmail.trim()) {
      setShareError('Укажите email зарегистрированного пользователя')
      return
    }

    if (selectedShareRecordIds.length === 0) {
      setShareError('Выберите хотя бы одну запись')
      return
    }

    setShareSubmitting(true)
    try {
      const result = await createShareRequest({
        to_user_email: shareEmail.trim(),
        record_ids: selectedShareRecordIds,
        message: shareMessage.trim() || undefined,
      })
      setShareResult(result)

      if (result.request) {
        setSelectedShareRecordIds([])
      }
    } catch (submitError: unknown) {
      setShareError(getErrorMessage(submitError, 'Не удалось отправить sharing-запрос'))
    } finally {
      setShareSubmitting(false)
    }
  }

  const closeShareModal = () => {
    setIsShareModalOpen(false)
    setShareEmail('')
    setShareMessage('')
    setShareResult(null)
    setShareError(null)
  }

  if (!id) {
    return null
  }

  if (isLoading && !currentPatient) {
    return <p className="mt-8 text-center text-gray-500">Загружаю карточку пациента...</p>
  }

  if (error) {
    return <p className="mt-8 text-center text-red-600">{error}</p>
  }

  if (!currentPatient) {
    return null
  }

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <Link
          to="/patients"
          className="mb-4 inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к списку пациентов
        </Link>

        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{currentPatient.fio}</h1>
            <p className="text-gray-500">ID карточки: {currentPatient.id}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              icon={<Share2 className="h-4 w-4" />}
              disabled={selectedShareRecordIds.length === 0}
              onClick={() => setIsShareModalOpen(true)}
            >
              Поделиться выбранными
            </Button>
            <Button onClick={() => setShowAddModal(true)}>Добавить запись</Button>
          </div>
        </div>
      </motion.div>

      {showAddModal && (
        <AddRecordModal
          patientId={id}
          onClose={() => {
            setShowAddModal(false)
            void fetchPatientRecords(id)
          }}
        />
      )}

      {isShareModalOpen && (
        <ShareRecordsModal
          selectedCount={selectedShareRecordIds.length}
          email={shareEmail}
          message={shareMessage}
          result={shareResult}
          error={shareError}
          isSubmitting={shareSubmitting}
          onEmailChange={setShareEmail}
          onMessageChange={setShareMessage}
          onSubmit={handleShareSubmit}
          onClose={closeShareModal}
        />
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card title="Пациент">
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-gray-500">ФИО</p>
              <p className="font-medium text-gray-900">{currentPatient.fio}</p>
            </div>
            <div>
              <p className="text-gray-500">Дата рождения</p>
              <p>{currentPatient.birthday ? format(new Date(currentPatient.birthday), 'dd.MM.yyyy') : 'Не указана'}</p>
            </div>
            <div>
              <p className="text-gray-500">Email</p>
              <p>{currentPatient.email || 'Не указан'}</p>
            </div>
            <div>
              <p className="text-gray-500">Телефон</p>
              <p>{currentPatient.phone || 'Не указан'}</p>
            </div>
          </div>
        </Card>

        <Card title="Сводка">
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-gray-500">Всего записей</p>
              <p className="text-2xl font-bold text-primary-600">{patientRecords.length}</p>
            </div>
            <div>
              <p className="text-gray-500">Последняя запись</p>
              <p>{currentPatient.lastVisit ? format(new Date(currentPatient.lastVisit), 'dd.MM.yyyy') : 'Не указана'}</p>
            </div>
            <div>
              <p className="text-gray-500">Статус карточки</p>
              <p className="capitalize">{currentPatient.status}</p>
            </div>
          </div>
        </Card>

        <Card title="Подсказка">
          <p className="text-sm text-gray-600">
            Выберите одну или несколько записей, чтобы отправить sharing-запрос зарегистрированному
            пользователю. Доступ появится только после принятия запроса.
          </p>
        </Card>
      </div>

      <Card title="Медицинские записи">
        {patientRecords.length === 0 ? (
          <p className="py-12 text-center text-gray-500">У этой карточки пока нет записей.</p>
        ) : (
          <div className="space-y-4">
            {patientRecords.map((record) => {
              const isOpen = selectedRecordId === record.id
              const detail = isOpen && activeRecord?.id === record.id ? activeRecord : null
              const isSelectedForShare = selectedShareRecordIds.includes(record.id)

              return (
                <div key={record.id} className="rounded-lg border border-gray-200">
                  <div className="border-b border-gray-100 px-5 py-2">
                    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={isSelectedForShare}
                        onChange={() => handleToggleShareRecord(record.id)}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      Выбрать для sharing
                    </label>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleOpenRecord(record)}
                    className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="h-4 w-4" />
                          {format(new Date(record.eventDate), 'dd.MM.yyyy')}
                        </span>
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs capitalize">
                          {record.recordType}
                        </span>
                        <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs capitalize text-primary-700">
                          {record.status}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        {record.title || 'Медицинская запись'}
                      </h3>
                      {record.clinicalSummary && <p className="text-sm text-gray-700">{record.clinicalSummary}</p>}
                      <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                        <span className="inline-flex items-center gap-1">
                          <Building2 className="h-4 w-4" />
                          {record.appointmentLocation || 'Место не указано'}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <Stethoscope className="h-4 w-4" />
                          {record.practitioner?.full_name || 'Врач не указан'}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <MessageSquare className="h-4 w-4" />
                          {record.commentsCount}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <FileText className="h-4 w-4" />
                          {record.attachmentsCount}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm font-medium text-primary-600">
                      {isOpen ? 'Скрыть детали' : 'Открыть детали'}
                    </span>
                  </button>

                  {isOpen && (
                    <div className="border-t border-gray-200 px-5 py-4">
                      {detail ? (
                        <div className="space-y-6">
                          <div>
                            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                              Типоспецифичные данные
                            </h4>
                            <pre className="overflow-x-auto rounded-lg bg-gray-50 p-4 text-sm text-gray-800">
                              {JSON.stringify(detail.payloadJson, null, 2)}
                            </pre>
                          </div>

                          <div>
                            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                              Комментарии
                            </h4>
                            {detail.comments.length === 0 ? (
                              <p className="text-sm text-gray-500">Комментариев пока нет.</p>
                            ) : (
                              <div className="space-y-3">
                                {detail.comments.map((comment) => (
                                  <div key={comment.id} className="rounded-lg bg-gray-50 px-4 py-3">
                                    <p className="text-sm text-gray-800">{comment.body}</p>
                                    <p className="mt-1 text-xs text-gray-500">
                                      Автор: {comment.author_user_id} ·{' '}
                                      {format(new Date(comment.created_at), 'dd.MM.yyyy HH:mm')}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}

                            {canComment && (
                              <div className="mt-4 space-y-2">
                                <textarea
                                  value={commentBody}
                                  onChange={(event) => setCommentBody(event.target.value)}
                                  rows={3}
                                  className="w-full rounded border p-2"
                                  placeholder="Добавить комментарий к записи"
                                />
                                {commentError && <p className="text-sm text-red-600">{commentError}</p>}
                                <div className="flex justify-end">
                                  <Button onClick={handleAddComment} disabled={commentSubmitting || !commentBody.trim()}>
                                    {commentSubmitting ? 'Отправляю...' : 'Добавить комментарий'}
                                  </Button>
                                </div>
                              </div>
                            )}
                          </div>

                          <div>
                            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                              Вложения
                            </h4>
                            {detail.attachments.length === 0 ? (
                              <p className="text-sm text-gray-500">Вложений пока нет.</p>
                            ) : (
                              <div className="space-y-2">
                                {detail.attachments.map((attachment) => (
                                  <div key={attachment.id} className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-700">
                                    <p className="font-medium">{attachment.storage_key}</p>
                                    <p className="text-gray-500">
                                      {attachment.category} · {attachment.mime_type} · {attachment.size_bytes} байт
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">Загружаю детали записи...</p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}

function ShareRecordsModal({
  selectedCount,
  email,
  message,
  result,
  error,
  isSubmitting,
  onEmailChange,
  onMessageChange,
  onSubmit,
  onClose,
}: {
  selectedCount: number
  email: string
  message: string
  result: CreateShareResult | null
  error: string | null
  isSubmitting: boolean
  onEmailChange: (value: string) => void
  onMessageChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Поделиться записями</h2>
            <p className="mt-1 text-sm text-gray-500">Выбрано записей: {selectedCount}</p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-800">
            Закрыть
          </button>
        </div>

        {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {result && (
          <div className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
            {result.request ? (
              <p>Sharing-запрос создан. Получатель увидит его во входящих.</p>
            ) : (
              <p>Новые записи не добавлены: у получателя уже есть доступ или активный запрос.</p>
            )}
            {result.skipped_record_ids.length > 0 && (
              <p className="mt-1">Пропущено записей: {result.skipped_record_ids.length}</p>
            )}
          </div>
        )}

        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Email получателя</span>
            <input
              type="email"
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              className="mt-1 w-full rounded border p-2"
              placeholder="doctor@example.com"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700">Сообщение</span>
            <textarea
              value={message}
              onChange={(event) => onMessageChange(event.target.value)}
              rows={4}
              className="mt-1 w-full rounded border p-2"
              placeholder="Короткий контекст для получателя"
            />
          </label>
        </div>

        <div className="mt-6 flex justify-end space-x-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
            Отмена
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Отправляю...' : 'Отправить запрос'}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default PatientDetailsPage
