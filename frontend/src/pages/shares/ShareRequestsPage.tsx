import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { format } from 'date-fns'
import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  Clock,
  FileText,
  Inbox,
  Send,
  User,
  X,
} from 'lucide-react'

import { Button } from '../../components/common/Button'
import { ShareRequest, ShareStatus, useShareRequestsStore } from '../../stores/shareRequestsStore'

type Tab = 'inbox' | 'outbox'

const statusConfig: Record<ShareStatus, { label: string; className: string }> = {
  pending: { label: 'Ожидает', className: 'bg-warning-50 text-warning-700 border-warning-200' },
  accepted: { label: 'Принят', className: 'bg-success-50 text-success-700 border-success-200' },
  declined: { label: 'Отклонён', className: 'bg-error-50 text-error-700 border-error-200' },
  cancelled: { label: 'Отменён', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  revoked: { label: 'Отозван', className: 'bg-gray-100 text-gray-600 border-gray-200' },
}

const formatDateTime = (date: string) => format(new Date(date), 'dd.MM.yyyy HH:mm')

const ShareRequestsPage = () => {
  const {
    inbox,
    outbox,
    isLoading,
    error,
    fetchInbox,
    fetchOutbox,
    acceptRequest,
    declineRequest,
    cancelRequest,
    revokeRequest,
  } = useShareRequestsStore()
  const [tab, setTab] = useState<Tab>('inbox')

  useEffect(() => {
    void fetchInbox()
    void fetchOutbox()
  }, [fetchInbox, fetchOutbox])

  const pendingInbox = inbox.filter((r) => r.status === 'pending').length
  const requests = tab === 'inbox' ? inbox : outbox

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sharing записей</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Управляйте входящими запросами и доступами, которые вы выдали другим пользователям.
          </p>
        </div>
      </motion.div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('inbox')}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
            tab === 'inbox'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
          }`}
        >
          <div className="flex items-center gap-2">
            <ArrowDownLeft className="h-4 w-4" />
            Входящие
            {pendingInbox > 0 && (
              <span className={`flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs font-bold ${
                tab === 'inbox' ? 'bg-white text-primary-600' : 'bg-error-500 text-white'
              }`}>
                {pendingInbox}
              </span>
            )}
          </div>
        </button>
        <button
          onClick={() => setTab('outbox')}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
            tab === 'outbox'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
          }`}
        >
          <ArrowUpRight className="h-4 w-4" />
          Исходящие
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700">
          {error}
        </div>
      )}

      {isLoading && requests.length === 0 ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="animate-pulse rounded-xl bg-white border border-gray-100 p-6 shadow-card">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-full bg-gray-200" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-48 rounded bg-gray-200" />
                  <div className="h-3 w-32 rounded bg-gray-200" />
                </div>
              </div>
              <div className="h-12 rounded-lg bg-gray-100" />
            </div>
          ))}
        </div>
      ) : requests.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white py-16 text-center"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
            {tab === 'inbox' ? <Inbox className="h-6 w-6 text-gray-400" /> : <Send className="h-6 w-6 text-gray-400" />}
          </div>
          <p className="mt-3 text-sm font-medium text-gray-900">
            {tab === 'inbox' ? 'Входящих запросов нет' : 'Исходящих запросов нет'}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            {tab === 'inbox'
              ? 'Когда кто-то поделится записями — они появятся здесь'
              : 'Поделитесь записями пациента из карточки пациента'}
          </p>
        </motion.div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {requests.map((request) => (
              <ShareRequestCard
                key={request.id}
                request={request}
                mode={tab}
                onAccept={() => acceptRequest(request.id)}
                onDecline={() => declineRequest(request.id)}
                onCancel={() => cancelRequest(request.id)}
                onRevoke={() => revokeRequest(request.id)}
              />
            ))}
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  )
}

function ShareRequestCard({
  request,
  mode,
  onAccept,
  onDecline,
  onCancel,
  onRevoke,
}: {
  request: ShareRequest
  mode: Tab
  onAccept: () => Promise<void>
  onDecline: () => Promise<void>
  onCancel: () => Promise<void>
  onRevoke: () => Promise<void>
}) {
  const counterparty = mode === 'inbox' ? request.from_user : request.to_user
  const status = statusConfig[request.status]
  const initials = counterparty.fio
    ? counterparty.fio.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase()
    : counterparty.email[0].toUpperCase()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-gray-100 bg-white shadow-card overflow-hidden"
    >
      {/* Left accent by status */}
      <div className={`h-1 w-full ${request.status === 'pending' ? 'bg-warning-400' : request.status === 'accepted' ? 'bg-success-400' : request.status === 'declined' ? 'bg-error-400' : 'bg-gray-200'}`} />

      <div className="p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-700">
              {initials}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold text-gray-900">{counterparty.fio}</h2>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 capitalize">
                  {counterparty.role}
                </span>
                <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${status.className}`}>
                  {status.label}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-500">{counterparty.email}</p>
              <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                <Clock className="h-3 w-3" />
                {formatDateTime(request.created_at)}
              </div>
              {request.message && (
                <p className="mt-2 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                  {request.message}
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 shrink-0">
            {mode === 'inbox' && request.status === 'pending' && (
              <>
                <Button size="sm" icon={<Check className="h-3.5 w-3.5" />} onClick={onAccept}>
                  Принять
                </Button>
                <Button size="sm" variant="outline" icon={<X className="h-3.5 w-3.5" />} onClick={onDecline}>
                  Отклонить
                </Button>
              </>
            )}
            {mode === 'outbox' && request.status === 'pending' && (
              <Button size="sm" variant="outline" onClick={onCancel}>Отменить</Button>
            )}
            {mode === 'outbox' && request.status === 'accepted' && (
              <Button size="sm" variant="danger" onClick={onRevoke}>Отозвать доступ</Button>
            )}
          </div>
        </div>

        {request.shares.length > 0 && (
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {request.shares.map((share) => (
              <div
                key={share.id}
                className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5"
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-gray-400" />
                  <div>
                    <p className="text-xs font-medium text-gray-900">Запись {share.record_id.slice(0, 8)}</p>
                    {share.patient_passport_id && (
                      <Link
                        to={`/patients/${share.patient_passport_id}`}
                        className="text-xs text-primary-600 hover:text-primary-700 hover:underline"
                      >
                        Открыть карточку
                      </Link>
                    )}
                  </div>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusConfig[share.status].className}`}>
                  {statusConfig[share.status].label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default ShareRequestsPage
