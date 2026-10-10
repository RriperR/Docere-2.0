import { useEffect, useState } from 'react'
import { ArrowUpRight, MessagesSquare } from 'lucide-react'
import { Link } from 'react-router-dom'
import { caseApi, caseError, type CaseView } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import CaseSummaryCard from '../cases/CaseSummaryCard'
import { secondaryButtonClass } from '../cases/styles'

export default function RecentCases() {
  const revision = useNotificationsStore(s => s.revision)
  const [items, setItems] = useState<CaseView[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setItems([])
    void caseApi.list('all', 'active', 0, controller.signal).then(page => {
      if (!controller.signal.aborted) setItems(page.items.slice(0, 2))
    }).catch(e => {
      if (!controller.signal.aborted) setError(caseError(e))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [revision, retry])
  return <section aria-labelledby="active-cases-title" className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="active-cases-title" className="text-lg font-semibold text-gray-900">Продолжить разбор</h2>
        <p className="mt-1 text-sm text-gray-500">Ваши активные случаи и приглашения коллег.</p></div>
      <Link to="/cases" className="flex items-center gap-1 text-sm font-semibold text-primary-700">Все случаи <ArrowUpRight size={16} aria-hidden="true" /></Link>
    </div>
    {loading && <p role="status" className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500">Загружаем активные случаи…</p>}
    {error && <p role="alert" className="rounded-2xl border border-error-200 bg-error-50 p-5 text-sm text-error-700">{error}
      <button className="ml-2 font-semibold underline" onClick={() => setRetry(value => value + 1)}>Повторить</button></p>}
    {!loading && !error && !items.length && <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-dashed border-primary-200 bg-primary-50/40 p-6">
      <MessagesSquare size={28} className="text-primary-600" aria-hidden="true" />
      <div className="min-w-0 flex-1"><h3 className="font-semibold">Пригласите коллегу к обсуждению</h3>
        <p className="mt-1 text-sm text-gray-600">Соберите материалы пациента и вопрос в одном клиническом случае.</p></div>
      <Link to="/cases/new" className={secondaryButtonClass}>Создать случай</Link>
    </div>}
    <div className="grid gap-4">{items.map(item => <CaseSummaryCard key={item.id} item={item} />)}</div>
  </section>
}
