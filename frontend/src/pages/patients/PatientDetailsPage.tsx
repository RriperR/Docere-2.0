import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Building2, Calendar, FileText, MessageSquare, Stethoscope } from 'lucide-react'
import { format } from 'date-fns'

import { AddRecordModal } from '../../components/AddRecordModal'
import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { useAuthStore } from '../../stores/authStore'
import { PatientRecordSummary, usePatientsStore } from '../../stores/patientsStore'

type ApiError = {
  response?: {
    data?: {
      detail?: string
    }
  }
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

  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
  const [commentBody, setCommentBody] = useState('')
  const [commentError, setCommentError] = useState<string | null>(null)
  const [commentSubmitting, setCommentSubmitting] = useState(false)

  useEffect(() => {
    if (id) {
      void fetchPatientById(id)
      void fetchPatientRecords(id)
      clearActiveRecord()
      setSelectedRecordId(null)
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
      const apiError = submitError as ApiError
      setCommentError(apiError.response?.data?.detail || 'Не удалось добавить комментарий')
    } finally {
      setCommentSubmitting(false)
    }
  }

  if (!id) {
    return null
  }

  if (isLoading && !currentPatient) {
    return <p className="mt-8 text-center text-gray-500">Загружаю карточку пациента…</p>
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
        <Link to="/patients" className="mb-4 inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к списку пациентов
        </Link>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{currentPatient.fio}</h1>
            <p className="text-gray-500">ID карточки: {currentPatient.id}</p>
          </div>
          <Button onClick={() => setShowAddModal(true)}>Добавить запись</Button>
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

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card title="Пациент">
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-gray-500">ФИО</p>
              <p className="font-medium text-gray-900">{currentPatient.fio}</p>
            </div>
            <div>
              <p className="text-gray-500">Дата рождения</p>
              <p>{currentPatient.birthday ? format(new Date(currentPatient.birthday), 'dd.MM.yyyy') : '—'}</p>
            </div>
            <div>
              <p className="text-gray-500">Email</p>
              <p>{currentPatient.email || '—'}</p>
            </div>
            <div>
              <p className="text-gray-500">Телефон</p>
              <p>{currentPatient.phone || '—'}</p>
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
              <p>{currentPatient.lastVisit ? format(new Date(currentPatient.lastVisit), 'dd.MM.yyyy') : '—'}</p>
            </div>
            <div>
              <p className="text-gray-500">Статус карточки</p>
              <p className="capitalize">{currentPatient.status}</p>
            </div>
          </div>
        </Card>

        <Card title="Подсказка">
          <p className="text-sm text-gray-600">
            Запись теперь immutable: её медицинское содержимое не редактируется после создания.
            Для обсуждения используйте комментарии.
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

              return (
                <div key={record.id} className="rounded-lg border border-gray-200">
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
                                      Автор: {comment.author_user_id} · {format(new Date(comment.created_at), 'dd.MM.yyyy HH:mm')}
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
                                    {commentSubmitting ? 'Отправляю…' : 'Добавить комментарий'}
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
                        <p className="text-sm text-gray-500">Загружаю детали записи…</p>
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

export default PatientDetailsPage
