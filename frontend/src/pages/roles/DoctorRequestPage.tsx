import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  Check,
  CheckCircle,
  Clock3,
  Stethoscope,
  UserCheck,
  XCircle,
} from 'lucide-react'

import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'
import {
  DoctorRoleApplication,
  DoctorRoleReviewerCandidate,
  useDoctorRoleApplicationsStore,
} from '../../stores/doctorRoleApplicationsStore'

const statusLabels = {
  pending: 'На проверке',
  approved: 'Одобрена',
  rejected: 'Отклонена',
}

const reviewStatusLabels = {
  pending: 'Ожидает решения',
  approved: 'Одобрено',
  rejected: 'Отклонено',
}

const DoctorRequestPage: React.FC = () => {
  const {
    specialties,
    reviewers,
    mine,
    isLoading,
    isSubmitting,
    error,
    fetchSpecialties,
    fetchReviewers,
    fetchMine,
    createApplication,
    clearReviewers,
    clearError,
  } = useDoctorRoleApplicationsStore()
  const [specialty, setSpecialty] = useState('')
  const [selectedReviewerIds, setSelectedReviewerIds] = useState<string[]>([])
  const [formError, setFormError] = useState<string | null>(null)
  const refreshUser = useAuthStore((state) => state.refreshUser)

  const pendingApplication = mine.find((application) => application.status === 'pending')

  useEffect(() => {
    void fetchMine()
    void fetchSpecialties()
  }, [fetchMine, fetchSpecialties])

  useEffect(() => {
    if (!pendingApplication) return
    const intervalId = window.setInterval(() => void fetchMine(), 15000)
    return () => window.clearInterval(intervalId)
  }, [fetchMine, pendingApplication])

  useEffect(() => {
    if (mine.some((application) => application.status === 'approved')) {
      void refreshUser()
    }
  }, [mine, refreshUser])

  useEffect(() => {
    setSelectedReviewerIds([])
    clearError()
    if (specialty.trim().length < 2) {
      clearReviewers()
      return
    }
    const timeoutId = window.setTimeout(() => void fetchReviewers(specialty), 300)
    return () => window.clearTimeout(timeoutId)
  }, [clearError, clearReviewers, fetchReviewers, specialty])

  const selectedReviewers = useMemo(
    () => reviewers.filter((reviewer) => selectedReviewerIds.includes(reviewer.id)),
    [reviewers, selectedReviewerIds],
  )
  const selectedAdmins = selectedReviewers.filter((reviewer) => reviewer.role === 'admin').length
  const selectedDoctors = selectedReviewers.filter((reviewer) => reviewer.role === 'doctor').length
  const quorumReady = selectedAdmins > 0 || selectedDoctors >= 2

  const toggleReviewer = (reviewer: DoctorRoleReviewerCandidate) => {
    setSelectedReviewerIds((current) =>
      current.includes(reviewer.id)
        ? current.filter((reviewerId) => reviewerId !== reviewer.id)
        : [...current, reviewer.id],
    )
    setFormError(null)
  }

  const submit = async () => {
    if (specialty.trim().length < 2) {
      setFormError('Укажите специализацию')
      return
    }
    if (!quorumReady) {
      setFormError('Выберите администратора или минимум двух врачей этой специализации')
      return
    }
    setFormError(null)
    await createApplication(specialty, selectedReviewerIds)
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-2">
          <Stethoscope className="h-6 w-6 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900">Заявка на роль врача</h1>
        </div>
        <p className="mt-1 text-sm text-gray-500">Выберите специализацию и тех, кто подтвердит вашу квалификацию</p>
      </motion.div>

      {(formError || error) && (
        <div className="flex items-start rounded-lg border border-error-200 bg-error-50 p-4">
          <AlertTriangle className="mr-2 mt-0.5 h-5 w-5 shrink-0 text-error-500" />
          <p className="text-sm text-error-700">{formError || error}</p>
        </div>
      )}

      {pendingApplication ? (
        <ApplicationProgress application={pendingApplication} />
      ) : (
        <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-100 px-5 py-4">
            <h2 className="font-semibold text-gray-900">Новая заявка</h2>
          </div>
          <div className="space-y-6 p-5">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-gray-700">Специализация</span>
              <input
                list="doctor-specialties"
                value={specialty}
                onChange={(event) => setSpecialty(event.target.value)}
                placeholder="Например, Кардиология"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
              />
              <datalist id="doctor-specialties">
                {specialties.map((value) => <option key={value} value={value} />)}
              </datalist>
            </label>

            {specialty.trim().length >= 2 && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">Проверяющие</h3>
                    <p className="text-xs text-gray-500">Администратор подтверждает один, либо нужны два врача специализации</p>
                  </div>
                  <QuorumBadge admins={selectedAdmins} doctors={selectedDoctors} ready={quorumReady} />
                </div>

                {isLoading && reviewers.length === 0 && (
                  <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">Загрузка проверяющих...</p>
                )}
                {!isLoading && reviewers.length === 0 && (
                  <p className="rounded-lg border border-warning-200 bg-warning-50 p-4 text-sm text-warning-700">
                    Для этой специализации пока нет доступных врачей или администраторов
                  </p>
                )}

                <div className="grid gap-3 md:grid-cols-2">
                  {reviewers.map((reviewer) => {
                    const selected = selectedReviewerIds.includes(reviewer.id)
                    return (
                      <label
                        key={reviewer.id}
                        className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                          selected ? 'border-primary-400 bg-primary-50' : 'border-gray-200 hover:border-primary-200'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleReviewer(reviewer)}
                          className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-gray-900">{reviewer.fio}</span>
                          <span className="block truncate text-xs text-gray-500">{reviewer.email}</span>
                          <span className="mt-1 inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                            {reviewer.role === 'admin' ? 'Администратор' : reviewer.specialty || 'Врач'}
                          </span>
                        </span>
                        {selected && <Check className="h-4 w-4 shrink-0 text-primary-600" />}
                      </label>
                    )
                  })}
                </div>
              </div>
            )}

            <div className="flex justify-end border-t border-gray-100 pt-4">
              <Button
                type="button"
                onClick={() => void submit()}
                disabled={!quorumReady || specialty.trim().length < 2}
                isLoading={isSubmitting}
                icon={<UserCheck className="h-4 w-4" />}
              >
                Отправить на проверку
              </Button>
            </div>
          </div>
        </section>
      )}

      {mine.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-100 px-5 py-4">
            <h2 className="font-semibold text-gray-900">История заявок</h2>
          </div>
          <div className="divide-y divide-gray-100">
            {mine.map((application) => (
              <div key={application.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{application.specialty}</p>
                  <p className="text-xs text-gray-500">{formatDateTime(application.created_at)}</p>
                </div>
                <ApplicationStatus status={application.status} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function ApplicationProgress({ application }: { application: DoctorRoleApplication }) {
  const approvedDoctors = application.reviews.filter(
    (review) => review.reviewer_role === 'doctor' && review.status === 'approved',
  ).length
  const approvedByAdmin = application.reviews.some(
    (review) => review.reviewer_role === 'admin' && review.status === 'approved',
  )

  return (
    <section className="overflow-hidden rounded-lg border border-primary-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-primary-100 bg-primary-50 px-5 py-4">
        <div>
          <p className="text-xs font-medium uppercase text-primary-600">Текущая заявка</p>
          <h2 className="mt-1 font-semibold text-gray-900">{application.specialty}</h2>
        </div>
        <ApplicationStatus status={application.status} />
      </div>
      <div className="space-y-4 p-5">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Clock3 className="h-4 w-4 text-primary-500" />
          {approvedByAdmin
            ? 'Заявку подтвердил администратор'
            : `Одобрений врачей: ${approvedDoctors} из 2`}
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {application.reviews.map((review) => (
            <div key={review.id} className="rounded-lg border border-gray-200 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-900">{review.reviewer_fio}</p>
                  <p className="truncate text-xs text-gray-500">{review.reviewer_email}</p>
                </div>
                <ReviewStatus status={review.status} />
              </div>
              <p className="mt-2 text-xs text-gray-500">
                {review.reviewer_role === 'admin' ? 'Администратор' : review.reviewer_specialty || 'Врач'}
              </p>
              {review.note && <p className="mt-2 text-sm text-gray-700">{review.note}</p>}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function QuorumBadge({ admins, doctors, ready }: { admins: number; doctors: number; ready: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${
      ready
        ? 'border-success-200 bg-success-50 text-success-700'
        : 'border-warning-200 bg-warning-50 text-warning-700'
    }`}>
      {ready ? <CheckCircle className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
      {ready ? 'Кворум выбран' : `Админов ${admins} · врачей ${doctors}/2`}
    </span>
  )
}

function ApplicationStatus({ status }: { status: DoctorRoleApplication['status'] }) {
  const styles = {
    pending: 'border-warning-200 bg-warning-50 text-warning-700',
    approved: 'border-success-200 bg-success-50 text-success-700',
    rejected: 'border-error-200 bg-error-50 text-error-700',
  }
  const icons = {
    pending: <Clock3 className="h-3.5 w-3.5" />,
    approved: <CheckCircle className="h-3.5 w-3.5" />,
    rejected: <XCircle className="h-3.5 w-3.5" />,
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${styles[status]}`}>
      {icons[status]}
      {statusLabels[status]}
    </span>
  )
}

function ReviewStatus({ status }: { status: 'pending' | 'approved' | 'rejected' }) {
  const styles = {
    pending: 'text-warning-700',
    approved: 'text-success-700',
    rejected: 'text-error-700',
  }
  return <span className={`shrink-0 text-xs font-medium ${styles[status]}`}>{reviewStatusLabels[status]}</span>
}

const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))

export default DoctorRequestPage
