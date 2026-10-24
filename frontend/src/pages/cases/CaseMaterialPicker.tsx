import { formatDateForDisplay } from '../../utils/dates'
import { useEffect, useState } from 'react'
import api from '../../api/api'
import { caseError, type Material, type Page } from '../../api/cases'
import { inputClass } from './styles'

/** Select references by title/date, with server pagination rather than loading the patient's history. */
export default function CaseMaterialPicker({ caseId, sequence, selected, multiple = false, onChange, onAccessLost }: {
  caseId: string; sequence: number; selected: string[]; multiple?: boolean
  onChange: (ids: string[]) => void; onAccessLost: () => Promise<void>
}) {
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<Page<Material>>({ items: [], total: 0 })
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void api.get<Page<Material>>(`/cases/${caseId}/materials`, { params: { query, offset, limit: 20 }, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) { setPage(result.data); setError('') } })
      .catch(e => { if (!controller.signal.aborted) { setPage({ items: [], total: 0 }); setError(caseError(e)); void onAccessLost() } })
    return () => controller.abort()
  }, [caseId, sequence, query, offset, onAccessLost])
  return <fieldset className="rounded-lg border p-3 space-y-2">
    <legend>{multiple ? 'Использованные материалы' : 'Связанный материал'}</legend>
    <input aria-label={multiple ? 'Поиск источников итога' : 'Поиск материала для сообщения'} className={inputClass}
      maxLength={200} placeholder="Название или описание материала" value={query}
      onChange={e => { setQuery(e.target.value); setOffset(0) }} />
    {error && <p role="alert">{error}</p>}
    {page.items.map(m => <label className="block" key={m.id}>
      <input type={multiple ? 'checkbox' : 'radio'} name={`reference-${caseId}-${multiple ? 'conclusion' : 'message'}`}
        checked={selected.includes(m.id)} onChange={e => onChange(multiple
          ? e.target.checked ? [...selected, m.id] : selected.filter(id => id !== m.id) : [m.id])} />
      {' '}{formatDateForDisplay(m.event_date)} · {m.title ?? 'Медицинская запись'}
    </label>)}
    <div className="flex flex-wrap gap-4"><button type="button" disabled={!offset} onClick={() => setOffset(offset - 20)}>Предыдущие материалы</button>
      <span>{selected.length} выбрано · {page.total} материалов</span>
      <button type="button" disabled={offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Следующие материалы</button>
      <button type="button" disabled={!selected.length} onClick={() => onChange([])}>Убрать ссылки</button></div>
  </fieldset>
}
