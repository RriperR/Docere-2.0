import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { caseApi, caseError, type CaseView } from '../../api/cases'

import { buttonClass, cardClass, inputClass, stateLabel } from './styles'

export default function CasesPage() {
  const [items, setItems] = useState<CaseView[]>([])
  const [scope, setScope] = useState('all')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try {
      const page = await caseApi.list(scope, status, offset)
      setItems(page.items); setTotal(page.total); setError('')
    } catch (e) { setItems([]); setError(caseError(e)) }
  }, [scope, status, offset])
  useEffect(() => { void load() }, [load])
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold">Клинические случаи</h1>
      <Link className={buttonClass} to="/cases/new">Создать случай</Link>
    </div>
    <div className="flex gap-3">
      <select aria-label="Участие" className={inputClass} value={scope}
        onChange={e => { setScope(e.target.value); setOffset(0) }}>
        <option value="all">Все мои случаи</option><option value="coordinator">Я координатор</option>
        <option value="participating">Участвую</option>
      </select>
      <select aria-label="Состояние" className={inputClass} value={status}
        onChange={e => { setStatus(e.target.value); setOffset(0) }}>
        <option value="">Все состояния</option><option value="active">Активные</option>
        <option value="closed">Завершённые</option><option value="draft">Черновики</option>
      </select>
      <button onClick={() => void load()}>Обновить</button>
    </div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!items.length && !error && <p>Пока нет случаев в выбранной категории.</p>}
    {items.map(item => <Link key={item.id} to={`/cases/${item.id}`} className={`${cardClass} block`}>
      <h2 className="font-semibold">{item.case?.title ?? (item.membership_status === 'pending' ? 'Приглашение в разбор' : 'Случай недоступен')}</h2>
      <p>{item.coordinator_name} · {stateLabel[item.status]} · {item.material_count} материалов</p>
      {item.case && <p>{item.case.question}</p>}
      {item.membership_status === 'pending' && <p>Ожидает вашего ответа</p>}
    </Link>)}
    <div className="flex gap-4"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Назад</button>
      <span>{total ? offset + 1 : 0}–{Math.min(offset + 20, total)} из {total}</span>
      <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>
  </div>
}
