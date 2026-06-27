import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock3,
  Mail,
  Search,
  ShieldCheck,
  Stethoscope,
  User,
  XCircle,
} from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Input } from '../../components/common/Input'
import { useAuthStore } from '../../stores/authStore'
import {
  DoctorRoleApplication,
  useDoctorRoleApplicationsStore,
} from '../../stores/doctorRoleApplicationsStore'
import { formatDateForDisplay } from '../../utils/dates'

const ReviewRequestsPage: React.FC = () => {
  const currentUserId = useAuthStore((state) => state.user?.id ?? null)
  const {
    inbox,
    isLoading,
    isSubmitting,
    error,
    fetchInbox,
    reviewApplication,
    clearError,
  } = useDoctorRoleApplicationsStore()
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [note, setNote] = useState('')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  useEffect(() => {
    void fetchInbox()
  }, [fetchInbox])

  const filteredInbox = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return inbox
    return inbox.filter((application) =>
      [application.applicant_fio, application.applicant_email, application.specialty]
        .join(' ')
        .toLowerCase()
        .includes(query),
    )
  }, [inbox, searchQuery])

  const selectedApplication = inbox.find((application) => application.id === selectedApplicationId) ?? null
  const ownReview = selectedApplication?.reviews.find((review) => review.reviewer_user_id === currentUserId)

  const submitDecision = async (decision: 'approved' | 'rejected') => {
    if (!selectedApplication) return
    if (
      decision === 'rejected' &&
      !window.confirm(`Отклонить заявку ${selectedApplication.applicant_fio}? Решение нельзя будет изменить.`)
    ) {
      return
    }
    clearError()
    const result = await reviewApplication(selectedApplication.id, decision, note.trim() || null)
    setSuccessMessage(
      result.status === 'approved'
        ? 'Заявка одобрена, пользователю выдана роль врача'
        : result.status === 'rejected'
          ? 'Заявка отклонена: необходимый кворум больше недостижим'
          : 'Решение сохранено, заявка ожидает остальных проверяющих',
    )
    setSelectedApplicationId(null)
    setNote('')
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900">Проверка заявок врачей</h1>
        </div>
        <p className="mt-1 text-sm text-gray-500">Заявки, в которых пациент выбрал вас проверяющим</p>
      </motion.div>

      {error && (
        <div className="flex items-start rounded-lg border border-error-200 bg-error-50 p-4">
          <AlertTriangle className="mr-2 mt-0.5 h-5 w-5 shrink-0 text-error-500" />
          <p className="text-sm text-error-700">{error}</p>
        </div>
      )}
      {successMessage && (
        <div className="flex items-start rounded-lg border border-success-200 bg-success-50 p-4">
          <CheckCircle className="mr-2 mt-0.5 h-5 w-5 shrink-0 text-success-600" />
          <p className="text-sm text-success-700">{successMessage}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-100 p-4">
            <Input
              placeholder="Поиск по ФИО, email или специализации"
              icon={<Search className="h-4 w-4" />}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          {isLoading && inbox.length === 0 && (
            <p className="p-6 text-center text-sm text-gray-500">Загрузка заявок...</p>
          )}
          {!isLoading && filteredInbox.length === 0 && (
            <div className="p-8 text-center">
              <CheckCircle className="mx-auto h-9 w-9 text-success-500" />
              <p className="mt-3 text-sm font-medium text-gray-900">Нет заявок, ожидающих вашего решения</p>
            </div>
          )}

          <div className="divide-y divide-gray-100">
            {filteredInbox.map((application) => {
              const selected = application.id === selectedApplicationId
              const pendingReviews = application.reviews.filter((review) => review.status === 'pending').length
              return (
                <button
                  key={application.id}
                  type="button"
                  onClick={() => {
                    setSelectedApplicationId(application.id)
                    setSuccessMessage(null)
                    setNote('')
                  }}
                  className={`w-full p-4 text-left transition-colors ${
                    selected ? 'bg-primary-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-gray-900">{application.applicant_fio}</p>
                      <p className="truncate text-xs text-gray-500">{application.applicant_email}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-warning-50 px-2 py-1 text-xs font-medium text-warning-700">
                      {pendingReviews} ожидают
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1">
                      <Stethoscope className="h-3.5 w-3.5" />
                      {application.specialty}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      {formatDateTime(application.created_at)}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        <section className="rounded-lg border border-gray-200 bg-white">
          {selectedApplication && ownReview ? (
            <div>
              <div className="border-b border-gray-100 p-5">
                <p className="text-xs font-medium uppercase text-primary-600">Заявка на роль врача</p>
                <h2 className="mt-1 text-lg font-semibold text-gray-900">{selectedApplication.applicant_fio}</h2>
              </div>
              <div className="space-y-5 p-5">
                <ApplicantDetails application={selectedApplication} />
                <ReviewProgress application={selectedApplication} currentUserId={currentUserId} />

                <label className="block space-y-1.5">
                  <span className="text-sm font-medium text-gray-700">Комментарий к решению</span>
                  <textarea
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    maxLength={2000}
                    rows={4}
                    placeholder="Основание решения (необязательно)"
                    className="w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
                  />
                </label>

                <div className="grid grid-cols-2 gap-3 border-t border-gray-100 pt-4">
                  <Button
                    variant="danger"
                    onClick={() => void submitDecision('rejected')}
                    disabled={ownReview.status !== 'pending'}
                    isLoading={isSubmitting}
                    icon={<XCircle className="h-4 w-4" />}
                  >
                    Отклонить
                  </Button>
                  <Button
                    onClick={() => void submitDecision('approved')}
                    disabled={ownReview.status !== 'pending'}
                    isLoading={isSubmitting}
                    icon={<CheckCircle className="h-4 w-4" />}
                  >
                    Одобрить
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-h-80 items-center justify-center p-8 text-center">
              <div>
                <User className="mx-auto h-10 w-10 text-gray-300" />
                <p className="mt-3 text-sm text-gray-500">Выберите заявку для проверки</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function ApplicantDetails({ application }: { application: DoctorRoleApplication }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-2 text-gray-700">
        <Mail className="h-4 w-4 text-gray-400" />
        <span className="break-all">{application.applicant_email}</span>
      </div>
      <div className="flex items-center gap-2 text-gray-700">
        <Stethoscope className="h-4 w-4 text-gray-400" />
        <span>{application.specialty}</span>
      </div>
      {application.applicant_date_of_birth && (
        <div className="flex items-center gap-2 text-gray-700">
          <Calendar className="h-4 w-4 text-gray-400" />
          <span>{formatDateForDisplay(application.applicant_date_of_birth)}</span>
        </div>
      )}
    </div>
  )
}

function ReviewProgress({ application, currentUserId }: { application: DoctorRoleApplication; currentUserId: string | null }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-gray-700">Выбранные проверяющие</p>
      <div className="space-y-2">
        {application.reviews.map((review) => (
          <div
            key={review.id}
            className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm ${
              review.reviewer_user_id === currentUserId ? 'border-primary-200 bg-primary-50' : 'border-gray-200'
            }`}
          >
            <div className="min-w-0">
              <p className="truncate font-medium text-gray-900">
                {review.reviewer_fio}{review.reviewer_user_id === currentUserId ? ' · вы' : ''}
              </p>
              <p className="text-xs text-gray-500">
                {review.reviewer_role === 'admin' ? 'Администратор' : review.reviewer_specialty || 'Врач'}
              </p>
            </div>
            {review.status === 'approved' ? (
              <CheckCircle className="h-4 w-4 shrink-0 text-success-600" />
            ) : review.status === 'rejected' ? (
              <XCircle className="h-4 w-4 shrink-0 text-error-600" />
            ) : (
              <Clock3 className="h-4 w-4 shrink-0 text-warning-600" />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))

export default ReviewRequestsPage
