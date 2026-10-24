import { useEffect, useState } from 'react'
import { ArrowRight, Check, FileCheck2, Inbox, MessageSquare, Share2, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getTasks, taskActions, taskLabels, taskPath, type InboxTask, type TaskKind } from '../../api/inbox'
import { caseError } from '../../api/cases'
import { useInboxStore } from '../../stores/inboxStore'
import { useAuthStore } from '../../stores/authStore'
import { importTaskContext } from '../../utils/importDisplay'

const icons: Record<TaskKind, typeof Inbox> = {
  invitation: Users, opinion_requested: MessageSquare, share_request: Share2, import_review: FileCheck2,
}

/** Показывает единую серверную очередь, не раскрывая сведения до принятия доступа. */
export default function DashboardInbox() {
  const accountId = useAuthStore(state => state.user?.id ?? null)
  const revision = useInboxStore(state => state.revision)
  const [items, setItems] = useState<InboxTask[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [settledKey, setSettledKey] = useState('')
  const requestKey = JSON.stringify([accountId, revision, retry])
  // Ключ скрывает старый контекст уже при рендере новой ревизии, до запуска эффекта.
  const pending = Boolean(accountId) && (loading || settledKey !== requestKey)

  useEffect(() => {
    setItems([]); setTotal(null); setError(''); setSettledKey('')
    if (!accountId) { setLoading(false); return }
    const controller = new AbortController()
    setLoading(true)
    void getTasks(0, 5, 'all', controller.signal).then(page => {
      if (!controller.signal.aborted) { setItems(page.items); setTotal(page.total) }
    }).catch(e => {
      if (!controller.signal.aborted) setError(caseError(e))
    }).finally(() => {
      if (!controller.signal.aborted) { setSettledKey(requestKey); setLoading(false) }
    })
    return () => controller.abort()
  }, [accountId, requestKey])

  return <section aria-labelledby="dashboard-inbox-title" aria-busy={pending} className="overflow-hidden rounded-2xl border border-primary-100 bg-white shadow-card">
    <div className="border-b border-gray-100 p-5 sm:p-6">
      <div className="flex items-center gap-2.5">
        <Inbox size={19} className="text-primary-600" aria-hidden="true" />
        <h2 id="dashboard-inbox-title" className="text-lg font-semibold text-gray-900">Входящие задачи</h2>
        {!pending && accountId && total !== null && total > 0 && <span className="ml-auto rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700" aria-label={`Всего задач: ${total}`}>{total}</span>}
      </div>
      <p className="mt-2 text-sm text-gray-500">Приглашения, мнения коллег и материалы на проверку.</p>
    </div>
    {!accountId ? <p className="p-5 text-sm text-gray-500 sm:p-6">Входящие доступны после входа в аккаунт.</p> : pending ? <p role="status" className="p-5 text-sm text-gray-500 sm:p-6">Проверяем входящие задачи…</p> : error ?
      <p role="alert" className="p-5 text-sm text-error-700 sm:p-6">{error} <button className="mt-3 block font-semibold underline" onClick={() => setRetry(value => value + 1)}>Повторить загрузку входящих</button></p> : !items.length ?
        <div className="p-5 sm:p-6"><div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-secondary-50 text-secondary-700"><Check size={20} aria-hidden="true" /></div>
          <h3 className="font-semibold text-gray-900">Всё разобрано</h3><p className="mt-1 text-sm leading-relaxed text-gray-500">Новые задачи появятся здесь. Можно продолжить текущий разбор или начать новый.</p></div> :
        <div className="divide-y divide-gray-100">{items.map(task => {
          const Icon = icons[task.kind]
          return <Link key={task.key} to={taskPath(task)} aria-label={taskActions[task.kind]} className="group flex gap-3 p-5 transition-colors hover:bg-primary-50/40 sm:p-6">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600"><Icon size={18} aria-hidden="true" /></div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-gray-900">{taskLabels[task.kind]}</h3>
              <p className="mt-1 break-words text-sm leading-relaxed text-gray-600">{task.actor_name}{task.actor_name && task.context ? ' · ' : ''}{task.kind === 'import_review' ? importTaskContext(task.context) : task.context}</p>
              <time dateTime={task.created_at} className="mt-1 block text-xs text-gray-500">{new Date(task.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}</time>
              <span className="mt-3 flex items-center gap-2 text-sm font-semibold text-primary-700">{taskActions[task.kind]}<ArrowRight size={15} aria-hidden="true" /></span>
            </div>
          </Link>
        })}</div>}
    <Link to="/notifications" className="flex min-h-12 items-center justify-between gap-2 border-t border-gray-100 px-5 py-3 text-sm font-semibold text-primary-700 hover:bg-primary-50 sm:px-6">Все входящие <ArrowRight size={16} aria-hidden="true" /></Link>
  </section>
}
