import { useEffect, useState } from 'react'
import { ArrowUpRight, ArrowRight, MessagesSquare } from 'lucide-react'
import { Link } from 'react-router-dom'
import { caseApi, caseError, type CaseView } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import CaseSummaryCard from '../cases/CaseSummaryCard'
import { secondaryButtonClass } from '../cases/styles'

export default function RecentCases({ needsPatient = false }: { needsPatient?: boolean }) {
  const revision = useNotificationsStore(s => s.revision)
  const [items, setItems] = useState<CaseView[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setItems([])
    void caseApi.list('all', 'active', 0, controller.signal).then(page => {
      if (!controller.signal.aborted) setItems([...page.items].sort((left, right) => right.unread_messages - left.unread_messages).slice(0, 2))
    }).catch(e => {
      if (!controller.signal.aborted) setError(caseError(e))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [revision, retry])
  return <section aria-labelledby="active-cases-title" className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="active-cases-title" className="text-lg font-semibold text-gray-900">Продолжить разбор</h2>
        <p className="mt-1 text-sm text-gray-500">Активные случаи. Сначала — с новыми сообщениями.</p></div>
      <Link to="/cases" className="flex min-h-10 items-center gap-1 text-sm font-semibold text-primary-700">Все случаи <ArrowUpRight size={16} aria-hidden="true" /></Link>
    </div>
    {loading && <p role="status" className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500">Загружаем активные случаи…</p>}
    {error && <p role="alert" className="rounded-2xl border border-error-200 bg-error-50 p-5 text-sm text-error-700">{error}
      <button className="ml-2 font-semibold underline" onClick={() => setRetry(value => value + 1)}>Повторить</button></p>}
    {!loading && !error && !items.length && <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card sm:p-6">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-secondary-50 text-secondary-700"><MessagesSquare size={23} aria-hidden="true" /></div>
      <h3 className="mt-4 font-semibold text-gray-900">{needsPatient ? 'Здесь будет ваш первый разбор' : 'Начните совместный разбор'}</h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-500">{needsPatient ? 'После добавления пациента выберите материалы и сформулируйте вопрос для коллеги.' : 'Выберите пациента и материалы, задайте вопрос коллеге. Обсуждение и итог останутся связаны с историей пациента.'}</p>
      {!needsPatient && <Link to="/cases/new" className={`${secondaryButtonClass} mt-5`}>Создать случай <ArrowRight size={16} aria-hidden="true" /></Link>}
    </div>}
    <div className="grid gap-4">{items.map(item => <CaseSummaryCard key={item.id} item={item} />)}</div>
  </section>
}
