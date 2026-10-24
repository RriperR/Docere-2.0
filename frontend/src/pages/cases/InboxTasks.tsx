import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTasks, taskActions, taskLabels, taskPath, type InboxTask } from '../../api/inbox'
import { caseError } from '../../api/cases'
import { useInboxStore } from '../../stores/inboxStore'
import { secondaryButtonClass } from './styles'
import { importTaskContext } from '../../utils/importDisplay'

export default function InboxTasks({ limit = 20, offset = 0, kind = 'all', onTotal }: {
  limit?: number; offset?: number; kind?: string; onTotal?: (value: number) => void
}) {
  const revision = useInboxStore(state => state.revision)
  const [items, setItems] = useState<InboxTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const total = useCallback((value: number) => onTotal?.(value), [onTotal])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void getTasks(offset, limit, kind, controller.signal).then(page => {
      if (controller.signal.aborted) return
      setItems(page.items); total(page.total); setError('')
    }).catch(e => { if (!controller.signal.aborted) { setItems([]); setError(caseError(e)) } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [offset, limit, kind, revision, retry, total])
  return <div className="space-y-3">
    {loading && <p role="status" className="text-sm text-gray-500">Проверяем входящие задачи…</p>}
    {error && <p role="alert">{error} <button className={secondaryButtonClass} onClick={() => setRetry(value => value + 1)}>Повторить</button></p>}
    {!loading && !error && !items.length && <p className="rounded-xl bg-gray-50 p-5 text-gray-500">Задач пока нет. Новые приглашения, запросы мнения и документы на проверке появятся здесь.</p>}
    {!loading && items.map(task => <article key={task.key} className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0"><h3 className="font-semibold">{taskLabels[task.kind]}</h3>
        <p className="break-words text-sm text-gray-600">{task.actor_name}{task.actor_name && task.context ? ' · ' : ''}{task.kind === 'import_review' ? importTaskContext(task.context) : task.context}</p>
        <time className="text-xs text-gray-500">{new Date(task.created_at).toLocaleString('ru-RU')}</time></div>
      <Link className={secondaryButtonClass} to={taskPath(task)}>{taskActions[task.kind]}</Link>
    </article>)}
  </div>
}
