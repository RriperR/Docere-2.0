import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../../api/api'
import { caseError, type Page } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import InboxTasks from './InboxTasks'
import { taskLabels, type TaskKind } from '../../api/inbox'
import { buttonClass, cardClass, secondaryButtonClass } from './styles'

interface Notification { id: string; case_id: string | null; subject_id: string | null; event_type: string; available: boolean; created_at: string; read_at: string | null }
const labels: Record<string, string> = {
  invitation: 'Приглашение в клинический разбор', accept: 'Врач принял приглашение', decline: 'Приглашение отклонено',
  opinion_requested: 'Новый запрос мнения', opinion_answered: 'Получен ответ на запрос', message_reply: 'Ответ на ваше сообщение',
  materials_added: 'Добавлены материалы', conclusion_updated: 'Новая версия итога', closed: 'Разбор завершён',
  participation_terminated: 'Участие врача прекращено', unavailable: 'Событие больше недоступно',
}
export default function NotificationsPage() {
  const revision = useNotificationsStore(s => s.revision)
  const refresh = useNotificationsStore(s => s.refresh)
  const unread = useNotificationsStore(s => s.unread)
  const [items, setItems] = useState<Notification[]>([])
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'events' ? 'events' : 'tasks'
  const kind = (params.get('kind') ?? '') in taskLabels ? params.get('kind')! : 'all'
  const unreadOnly = params.get('unread') === 'true'
  const offset = Math.max(0, parseInt(params.get('offset') ?? '0', 10) || 0)
  const update = (key: string, value: string) => setParams(previous => { setTaskTotal(null); const next = new URLSearchParams(previous); next.set(key, value); if (key !== 'offset') next.delete('offset'); return next })
  const setOffset = (value: number) => update('offset', String(value))
  const [taskTotal, setTaskTotal] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    if (tab !== 'events') return
    setLoading(true)
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    try { const page = (await api.get<Page<Notification>>('/notifications', { params: { offset, limit: 20, unread_only: unreadOnly }, signal: controller.signal })).data
      if (controller.signal.aborted) return
      setItems(page.items); setTotal(page.total); setError('')
    } catch (e) { if (controller.signal.aborted) return; setItems([]); setError(caseError(e)) }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }, [offset, tab, unreadOnly])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, revision])
  async function read(path: string) {
    try { await api.post(`/notifications/${path}`); await refresh(); await load() } catch (e) { setError(caseError(e)) }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold">Входящие</h1>
    <p className="text-sm text-gray-600">Здесь — задачи, требующие вашего решения, и события разборов. Передачей отдельных записей можно управлять в разделе <Link className="text-primary-700 underline" to="/share-requests">«Доступ к записям»</Link>.</p>
    <nav aria-label="Разделы входящих" className="flex gap-3"><button aria-pressed={tab === 'tasks'} className={tab === 'tasks' ? buttonClass : secondaryButtonClass} onClick={() => update('tab', 'tasks')}>Требует действия</button><button aria-pressed={tab === 'events'} className={tab === 'events' ? buttonClass : secondaryButtonClass} onClick={() => update('tab', 'events')}>События</button></nav>
    {tab === 'tasks' ? <><label>Тип задачи<select className="ml-3 rounded-lg border p-2" value={kind} onChange={e => update('kind', e.target.value)}><option value="all">Все задачи</option>{Object.entries(taskLabels).map(([key, title]) => <option key={key} value={key as TaskKind}>{title}</option>)}</select></label><InboxTasks offset={offset} kind={kind} onTotal={setTaskTotal} />{taskTotal !== null && <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Назад</button><span>{taskTotal} задач</span><button disabled={taskTotal === null || offset + 20 >= taskTotal} onClick={() => setOffset(offset + 20)}>Далее</button></div>}</> : <>
    <label><input type="checkbox" checked={unreadOnly} onChange={e => update('unread', String(e.target.checked))} /> Только непрочитанные</label>
    <p>Прочтение уведомления не означает принятия приглашения или выполнения запроса.</p>
    <button className={buttonClass} disabled={!unread} onClick={() => void read('read-all')}>Прочитать все ({unread})</button>
    {error && <p role="alert" className="text-red-700">{error} <button className="underline" onClick={() => void load()}>Повторить</button></p>}
    {loading && <p role="status">Загружаем события…</p>}
    {!loading && !error && !items.length && <p>Событий пока нет.</p>}
    {!loading && items.map(n => <article key={n.id} className={cardClass}>
      <p className="font-semibold">{labels[n.event_type] ?? 'Изменение клинического случая'}</p>
      <p>{new Date(n.created_at).toLocaleString('ru-RU')} · {n.read_at ? 'Прочитано' : 'Новое'}</p>
      {n.available && n.case_id && <Link className="text-primary-700 underline" to={`/cases/${n.case_id}`}>Открыть случай</Link>}
      {!n.read_at && <button className="ml-4" onClick={() => void read(`${n.id}/read`)}>Отметить прочитанным</button>}
    </article>)}
    {!loading && !error && <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Назад</button><span>{total} уведомлений</span>
      <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>}</>}
  </div>
}
