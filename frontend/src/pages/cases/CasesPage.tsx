import { useCallback, useEffect, useRef, useState } from 'react'
import { FolderOpen, Plus, RefreshCw, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { caseApi, caseError, type CaseView } from '../../api/cases'
import { useNotificationsStore } from '../../stores/notificationsStore'
import CaseSummaryCard from './CaseSummaryCard'
import { buttonClass, inputClass, secondaryButtonClass } from './styles'

const scopes = [{ value: 'all', label: 'Все мои случаи' }, { value: 'coordinator', label: 'Я координатор' },
  { value: 'participating', label: 'Участвую' }]

export default function CasesPage() {
  const revision = useNotificationsStore(s => s.revision)
  const [items, setItems] = useState<CaseView[]>([])
  const [scope, setScope] = useState('all')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    setLoading(true); setError(''); setItems([])
    try {
      const page = await caseApi.list(scope, status, offset, controller.signal)
      if (controller.signal.aborted) return
      setItems(page.items); setTotal(page.total)
    } catch (e) {
      if (controller.signal.aborted) return
      setItems([]); setTotal(0); setError(caseError(e))
    } finally { if (!controller.signal.aborted) setLoading(false) }
  }, [scope, status, offset])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, revision])
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary-700">Совместная работа</p>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Клинические случаи</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-500">Материалы пациента, мнения коллег и итог разбора — в одном контексте.</p>
      </div>
      <Link className={buttonClass} to="/cases/new"><Plus size={18} aria-hidden="true" />Создать случай</Link>
    </div>
    <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-gray-200 bg-white p-4">
      <div role="group" aria-label="Участие" className="flex flex-wrap gap-1 rounded-xl bg-gray-100 p-1">
        {scopes.map(option => <button key={option.value} aria-pressed={scope === option.value}
          className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${scope === option.value ? 'bg-white text-primary-700 shadow-xs' : 'text-gray-600 hover:text-gray-900'}`}
          onClick={() => { setScope(option.value); setOffset(0) }}>{option.label}</button>)}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-gray-500">Состояние
          <select className={`${inputClass} mt-1`} value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }}>
            <option value="">Все состояния</option><option value="active">Активные</option>
            <option value="closed">Завершённые</option><option value="draft">Черновики</option>
          </select>
        </label>
        <button className={secondaryButtonClass} onClick={() => void load()} disabled={loading}>
          <RefreshCw size={16} aria-hidden="true" />Обновить</button>
      </div>
    </div>
    {error && <div role="alert" className="rounded-xl border border-error-200 bg-error-50 p-4 text-sm text-error-700">
      {error} <button className="ml-2 font-semibold underline" onClick={() => void load()}>Повторить</button></div>}
    {loading && <div role="status" className="rounded-2xl border border-gray-200 bg-white p-8 text-sm text-gray-500">Загружаем клинические случаи…</div>}
    {!loading && !items.length && !error && <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50 text-primary-600">
        {scope === 'all' && !status ? <Users size={26} aria-hidden="true" /> : <FolderOpen size={26} aria-hidden="true" />}</div>
      <h2 className="text-lg font-semibold">{scope === 'all' && !status ? 'Начните первый совместный разбор' : 'В этой категории пока нет случаев'}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-gray-500">
        {scope === 'all' && !status ? 'Выберите пациента и материалы, сформулируйте вопрос и пригласите коллегу. Черновик будет виден только вам.' : 'Измените фильтры, чтобы увидеть остальные разборы.'}</p>
      {scope === 'all' && !status ? <Link className={`${buttonClass} mt-6`} to="/cases/new">Создать первый случай</Link> :
        <button className={`${secondaryButtonClass} mt-6`} onClick={() => { setScope('all'); setStatus(''); setOffset(0) }}>Сбросить фильтры</button>}
    </div>}
    {!loading && <div className="grid gap-4 xl:grid-cols-2">{items.map(item => <CaseSummaryCard key={item.id} item={item} />)}</div>}
    {!loading && !error && total > 0 && <nav aria-label="Страницы клинических случаев" className="flex flex-wrap items-center justify-between gap-3 text-sm text-gray-500">
      <span>{offset + 1}–{Math.min(offset + items.length, total)} из {total}</span>
      {total > 20 && <div className="flex gap-2"><button className={secondaryButtonClass} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Назад</button>
        <button className={secondaryButtonClass} disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>}
    </nav>}
  </div>
}
