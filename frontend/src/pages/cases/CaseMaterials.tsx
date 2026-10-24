import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../api/api'
import { caseApi, caseError, type ClinicalCase, type Material, type Page } from '../../api/cases'
import { buttonClass, cardClass, inputClass, recordTypeLabel, recordStatusLabel } from './styles'
import { DateInput } from '../../components/common/DateInput'
import { formatDateForDisplay } from '../../utils/dates'
import type { Message } from './CaseDiscussion'

export default function CaseMaterials({ c, owner, onChange, onOpen }: {
  c: ClinicalCase; owner: boolean; onChange: () => Promise<void>; onOpen: (id: string, attachment: string | null) => void
}) {
  const [items, setItems] = useState<Material[]>([])
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [hits, setHits] = useState<Message[]>([])
  const [hitOffset, setHitOffset] = useState(0)
  const [hitTotal, setHitTotal] = useState(0)
  const [available, setAvailable] = useState<Material[]>([])
  const [availableOffset, setAvailableOffset] = useState(0)
  const [availableTotal, setAvailableTotal] = useState(0)
  const [selection, setSelection] = useState<string[]>([])
  const [adding, setAdding] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(c.title)
  const [question, setQuestion] = useState(c.question)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    try {
      const page = (await api.get<Page<Material>>(`/cases/${c.id}/materials`, { params: { query, offset, limit: 20,
        record_type: type || undefined, status: status || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }, signal: controller.signal })).data
      if (controller.signal.aborted) return
      setItems(page.items); setTotal(page.total)
      if (query) {
        const msg = (await api.get<Page<Message>>(`/cases/${c.id}/messages`, { params: { query, offset: hitOffset, limit: 10 }, signal: controller.signal })).data
        if (controller.signal.aborted) return
        setHits(msg.items); setHitTotal(msg.total)
      } else { setHits([]); setHitTotal(0) }
    } catch (e) { if (controller.signal.aborted) return; setItems([]); setHits([]); setError(caseError(e)); await onChange() }
  }, [c.id, query, type, status, dateFrom, dateTo, offset, hitOffset, onChange])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, c.sequence])
  useEffect(() => {
    if (!adding && !editing) return
    let cancelled = false
    void caseApi.available(c.patient_id, '', availableOffset).then(page => {
      if (!cancelled) { setAvailable(page.items); setAvailableTotal(page.total) }
    }).catch(e => { if (!cancelled) setError(caseError(e)) })
    return () => { cancelled = true }
  }, [adding, editing, c.patient_id, availableOffset])
  async function save() {
    setBusy(true); setError('')
    try {
      if (editing) await api.patch(`/cases/${c.id}`, { version: c.version, title, question, record_ids: selection })
      else await api.post(`/cases/${c.id}/materials`, { version: c.version, record_ids: selection })
      setAdding(false); setEditing(false); setConfirm(false); setSelection([]); await onChange()
    } catch (e) { setError(caseError(e)); await onChange() } finally { setBusy(false) }
  }
  return <section id="materials" className={cardClass}>
    <h2 className="text-lg font-semibold">Материалы пациента</h2>
    <p className="text-sm text-gray-500">Хронология выбранных записей. Остальная история пациента не открывается участникам.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <label className="block">Поиск в материалах и обсуждении<input className={inputClass} maxLength={200} value={query}
      onChange={e => { setQuery(e.target.value); setOffset(0); setHitOffset(0) }} placeholder="Название, описание, имя вложения или сообщение" /></label>
    <details className="rounded-xl border border-gray-200 p-3"><summary className="cursor-pointer text-sm font-medium">Фильтры ({[type, status, dateFrom, dateTo].filter(Boolean).length})</summary>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <select aria-label="Тип записи" className={inputClass} value={type} onChange={e => { setType(e.target.value); setOffset(0) }}>
        <option value="">Все типы</option><option value="consultation_result">Консультации</option><option value="exam_result">Обследования</option>
        <option value="lab_result">Анализы</option><option value="other">Другое</option></select>
      <select aria-label="Подтверждение" className={inputClass} value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }}>
        <option value="">Любой статус</option><option value="confirmed">Подтверждённые</option><option value="unconfirmed">Неподтверждённые</option></select>
      <label>Событие с<DateInput className={inputClass} value={dateFrom} onChange={value => { setDateFrom(value ?? ''); setOffset(0) }} /></label>
      <label>По дату<DateInput className={inputClass} value={dateTo} onChange={value => { setDateTo(value ?? ''); setOffset(0) }} /></label>
    </div>
    {[type, status, dateFrom, dateTo].some(Boolean) && <button className="mt-3 text-sm text-primary-700 underline" onClick={() => { setType(''); setStatus(''); setDateFrom(''); setDateTo(''); setOffset(0) }}>Сбросить фильтры</button>}
    </details>
    {items.map(m => <button key={m.id} className="block w-full rounded-lg border p-3 text-left space-y-1" onClick={() => onOpen(m.id, null)}>
      <p className="font-medium">{formatDateForDisplay(m.event_date)} · {m.title ?? 'Медицинская запись'}</p>
      <p className="text-sm text-gray-500">{recordTypeLabel[m.record_type] ?? 'Медицинская запись'} · {recordStatusLabel[m.status] ?? 'Статус неизвестен'}</p><p>{m.clinical_summary}</p>
    </button>)}
    {!items.length && <p>Материалов по выбранным условиям нет.</p>}
    <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Назад</button><span>{total} материалов</span>
      <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>
    {query && <div className="space-y-2"><h3 className="font-semibold">Совпадения в обсуждении ({hitTotal})</h3>
      <p className="text-sm text-gray-500">Фильтры типа, даты и подтверждения относятся к медицинским записям.</p>
      {hits.map(m => <article key={m.id} className="rounded-lg bg-gray-50 p-3"><p>{m.author_name}: {m.body}</p>
        {m.record_id && <button onClick={() => onOpen(m.record_id!, m.attachment_id)}>Открыть материал сообщения</button>}</article>)}
      <div className="flex gap-4"><button disabled={!hitOffset} onClick={() => setHitOffset(hitOffset - 10)}>Назад</button>
        <button disabled={hitOffset + 10 >= hitTotal} onClick={() => setHitOffset(hitOffset + 10)}>Далее</button></div>
    </div>}
    {owner && c.status !== 'closed' && <div className="space-y-3">
      <button className={buttonClass} onClick={() => { setAdding(true); setEditing(false); setSelection([]); setConfirm(false); setAvailableOffset(0) }}>Добавить материалы</button>
      {c.status === 'draft' && <button className="ml-4" onClick={() => {
        setEditing(true); setAdding(false); setSelection([...c.record_ids]); setTitle(c.title); setQuestion(c.question); setAvailableOffset(0)
      }}>Редактировать черновик</button>}
      {(adding || editing) && <div className="rounded-lg border p-4 space-y-3">
        {editing && <><label>Название<input className={inputClass} maxLength={255} value={title} onChange={e => setTitle(e.target.value)} /></label>
          <label>Вопрос<textarea className={inputClass} maxLength={10000} value={question} onChange={e => setQuestion(e.target.value)} /></label></>}
        {available.filter(m => editing || !c.record_ids.includes(m.id)).map(m => <label key={m.id} className="block">
          <input type="checkbox" checked={selection.includes(m.id)} onChange={e => setSelection(e.target.checked ? [...selection, m.id] : selection.filter(id => id !== m.id))} /> {formatDateForDisplay(m.event_date)} · {m.title}</label>)}
        <div className="flex gap-4"><button disabled={!availableOffset} onClick={() => setAvailableOffset(availableOffset - 20)}>Назад</button>
          <span>{availableTotal} доступных записей</span><button disabled={availableOffset + 20 >= availableTotal} onClick={() => setAvailableOffset(availableOffset + 20)}>Далее</button></div>
        <button className={buttonClass} disabled={busy || (!editing && !selection.length) || (editing && (!title.trim() || !question.trim()))}
          onClick={() => editing ? void save() : setConfirm(true)}>{editing ? 'Сохранить черновик' : 'Продолжить добавление'}</button>
        <button onClick={() => { setAdding(false); setEditing(false); setConfirm(false) }}>Отмена</button>
        {confirm && <div role="region" aria-label="Доступ к новым материалам" className="rounded-lg bg-primary-50 p-4 space-y-3">
          <p>Будет добавлено материалов: {selection.length}. Они станут доступны следующим участникам:</p>
          {c.members.filter(m => m.status === 'accepted').map(m => <p key={m.user_id}>{m.name}</p>)}
          {!c.members.some(m => m.status === 'accepted') && <p>Пока действующих участников нет. Принявшие приглашение получат актуальный набор.</p>}
          <button className={buttonClass} disabled={busy} onClick={() => void save()}>Подтвердить добавление материалов</button>
        </div>}
      </div>}
    </div>}
  </section>
}
