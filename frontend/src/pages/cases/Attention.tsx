import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/api'
import { caseError, type Page } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import { cardClass } from './styles'

interface Task { case_id: string | null; subject_id: string | null; event_type: string; available: boolean }

export default function Attention() {
  const revision = useNotificationsStore(s => s.revision)
  const [tasks, setTasks] = useState<Task[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try { const page = (await api.get<Page<Task>>('/notifications/attention', { params: { offset, limit: 10 } })).data
      setTasks(page.items); setTotal(page.total); setError('')
    } catch (e) { setTasks([]); setError(caseError(e)) }
  }, [offset])
  useEffect(() => { void load() }, [load, revision])
  return <section className={cardClass}>
    <div className="flex justify-between"><h2 className="text-lg font-semibold">Требует внимания</h2>
      <Link className="text-primary-700 underline" to="/notifications">Центр уведомлений</Link></div>
    {error && <p role="alert">{error}</p>}
    {!tasks.length && !error && <p>Приглашений и запросов, ожидающих ответа, нет.</p>}
    {tasks.map((t, index) => <div key={`${t.case_id}-${t.subject_id}-${index}`}>
      {t.available && t.case_id ? <Link className="text-primary-700" to={`/cases/${t.case_id}${t.event_type === 'opinion_requested' ? '#opinions' : ''}`}>
        {t.event_type === 'invitation' ? 'Ответить на приглашение в клинический разбор' : 'Ответить на запрос мнения'}</Link> : <p>Задача недоступна</p>}
    </div>)}
    <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 10)}>Назад</button>
      <span>{total} задач</span><button disabled={offset + 10 >= total} onClick={() => setOffset(offset + 10)}>Далее</button></div>
  </section>
}
