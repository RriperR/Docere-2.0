import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/api'
import { caseError, type Page } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import Attention from './Attention'
import { buttonClass, cardClass } from './styles'

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
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try { const page = (await api.get<Page<Notification>>('/notifications', { params: { offset, limit: 20 } })).data
      setItems(page.items); setTotal(page.total); setError('')
    } catch (e) { setItems([]); setError(caseError(e)) }
  }, [offset])
  useEffect(() => { void load() }, [load, revision])
  async function read(path: string) {
    try { await api.post(`/notifications/${path}`); await refresh(); await load() } catch (e) { setError(caseError(e)) }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold">Уведомления</h1><Attention />
    <p>Прочтение уведомления не означает принятия приглашения или выполнения запроса.</p>
    <button className={buttonClass} disabled={!unread} onClick={() => void read('read-all')}>Прочитать все ({unread})</button>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {items.map(n => <article key={n.id} className={cardClass}>
      <p className="font-semibold">{labels[n.event_type] ?? 'Изменение клинического случая'}</p>
      <p>{new Date(n.created_at).toLocaleString('ru-RU')} · {n.read_at ? 'Прочитано' : 'Новое'}</p>
      {n.available && n.case_id && <Link className="text-primary-700 underline" to={`/cases/${n.case_id}`}>Открыть случай</Link>}
      {!n.read_at && <button className="ml-4" onClick={() => void read(`${n.id}/read`)}>Отметить прочитанным</button>}
    </article>)}
    <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Назад</button><span>{total} уведомлений</span>
      <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>
  </div>
}
