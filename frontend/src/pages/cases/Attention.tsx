import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/api'
import { caseError, type Page } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import { CheckCircle2, ArrowUpRight, MessageSquare } from 'lucide-react'
import { cardClass, secondaryButtonClass } from './styles'

interface Task { case_id: string | null; subject_id: string | null; event_type: string; available: boolean }

export default function Attention() {
  const revision = useNotificationsStore(s => s.revision)
  const [tasks, setTasks] = useState<Task[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    setLoading(true)
    try { const page = (await api.get<Page<Task>>('/notifications/attention', { params: { offset, limit: 10 }, signal: controller.signal })).data
      if (controller.signal.aborted) return
      setTasks(page.items); setTotal(page.total); setError('')
    } catch (e) { if (controller.signal.aborted) return; setTasks([]); setError(caseError(e)) }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }, [offset])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, revision])
  return <section className={cardClass}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Требует внимания</h2>
      <Link className="flex items-center gap-1 text-sm font-semibold text-primary-700" to="/notifications">Центр уведомлений <ArrowUpRight size={16} aria-hidden="true" /></Link></div>
    {error && <p role="alert" className="text-sm text-error-700">{error} <button className="underline" onClick={() => void load()}>Повторить</button></p>}
    {loading && <p role="status" className="text-sm text-gray-500">Проверяем приглашения и запросы…</p>}
    {!loading && !tasks.length && !error && <p className="flex items-center gap-2 text-sm text-gray-500"><CheckCircle2 size={18} className="shrink-0 text-secondary-600" aria-hidden="true" />Новых приглашений и запросов мнения нет.</p>}
    {!loading && tasks.map((t, index) => <div key={`${t.case_id}-${t.subject_id}-${index}`}>
      {t.available && t.case_id ? <Link className="flex items-center gap-3 rounded-xl bg-primary-50 p-3 text-sm font-medium text-primary-800 hover:bg-primary-100" to={`/cases/${t.case_id}${t.event_type === 'opinion_requested' ? '#opinions' : ''}`}>
        <MessageSquare size={18} className="shrink-0" aria-hidden="true" />{t.event_type === 'invitation' ? 'Ответить на приглашение в клинический разбор' : 'Ответить на запрос мнения'}</Link> : <p className="text-sm text-gray-500">Задача недоступна</p>}
    </div>)}
    {!loading && total > 10 && <nav aria-label="Страницы задач" className="flex flex-wrap items-center gap-3 text-sm"><button className={secondaryButtonClass} disabled={!offset} onClick={() => setOffset(offset - 10)}>Назад</button>
      <span>{total} задач</span><button className={secondaryButtonClass} disabled={offset + 10 >= total} onClick={() => setOffset(offset + 10)}>Далее</button></nav>}
  </section>
}
