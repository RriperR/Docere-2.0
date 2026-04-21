import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { Inbox, Send } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { ShareRequest, ShareStatus, useShareRequestsStore } from '../../stores/shareRequestsStore'

type Tab = 'inbox' | 'outbox'

const statusLabel: Record<ShareStatus, string> = {
  pending: 'Ожидает ответа',
  accepted: 'Принят',
  declined: 'Отклонён',
  cancelled: 'Отменён',
  revoked: 'Отозван',
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

  const requests = tab === 'inbox' ? inbox : outbox

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sharing записей</h1>
        <p className="mt-1 text-gray-500">
          Управляйте входящими запросами и доступами, которые вы выдали другим пользователям.
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant={tab === 'inbox' ? 'primary' : 'outline'}
          icon={<Inbox className="h-4 w-4" />}
          onClick={() => setTab('inbox')}
        >
          Входящие
        </Button>
        <Button
          variant={tab === 'outbox' ? 'primary' : 'outline'}
          icon={<Send className="h-4 w-4" />}
          onClick={() => setTab('outbox')}
        >
          Исходящие
        </Button>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {isLoading && requests.length === 0 ? (
        <p className="py-12 text-center text-gray-500">Загружаю sharing-запросы...</p>
      ) : requests.length === 0 ? (
        <p className="py-12 text-center text-gray-500">Запросов пока нет.</p>
      ) : (
        <div className="space-y-4">
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
        </div>
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

  return (
    <Card>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">{counterparty.fio}</h2>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
              {counterparty.role}
            </span>
            <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs text-primary-700">
              {statusLabel[request.status]}
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-500">{counterparty.email}</p>
          <p className="mt-1 text-sm text-gray-500">Создан: {formatDateTime(request.created_at)}</p>
          {request.message && <p className="mt-3 text-sm text-gray-700">{request.message}</p>}
        </div>

        <div className="flex flex-wrap gap-2">
          {mode === 'inbox' && request.status === 'pending' && (
            <>
              <Button size="sm" onClick={onAccept}>
                Принять
              </Button>
              <Button size="sm" variant="outline" onClick={onDecline}>
                Отклонить
              </Button>
            </>
          )}
          {mode === 'outbox' && request.status === 'pending' && (
            <Button size="sm" variant="outline" onClick={onCancel}>
              Отменить
            </Button>
          )}
          {mode === 'outbox' && request.status === 'accepted' && (
            <Button size="sm" variant="outline" onClick={onRevoke}>
              Отозвать доступ
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {request.shares.map((share) => (
          <div
            key={share.id}
            className="flex flex-col rounded-lg bg-gray-50 px-4 py-3 text-sm md:flex-row md:items-center md:justify-between"
          >
            <div>
              <p className="font-medium text-gray-900">Запись {share.record_id}</p>
              {share.patient_passport_id && (
                <Link
                  to={`/patients/${share.patient_passport_id}`}
                  className="text-primary-600 hover:text-primary-700"
                >
                  Открыть карточку пациента
                </Link>
              )}
            </div>
            <span className="mt-2 rounded-full bg-white px-2 py-0.5 text-xs text-gray-700 md:mt-0">
              {statusLabel[share.status]}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default ShareRequestsPage
