import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import CaseMaterialPicker from './CaseMaterialPicker'
import api from '../../api/api'
import { caseError, type ClinicalCase, type Page } from '../../api/cases'
import { buttonClass, cardClass, inputClass } from './styles'

interface Conclusion { id: string; number: number; author_id: string; summary: string; findings: string; next_actions: string; source_ids: string[]; created_at: string }
interface Preview { title: string; clinical_summary: string; conclusion_version: number; published_record_id: string | null }

export default function CaseConclusion({ c, owner, onChange, onOpen }: {
  c: ClinicalCase; owner: boolean; onChange: () => Promise<void>; onOpen?: (id: string) => void
}) {
  const [items, setItems] = useState<Conclusion[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [summary, setSummary] = useState('')
  const [findings, setFindings] = useState('')
  const [actions, setActions] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [edit, setEdit] = useState(false)
  const [openRequests, setOpenRequests] = useState<number | null>(null)
  const [cancelRequests, setCancelRequests] = useState(false)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [eventDate, setEventDate] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    try { const page = (await api.get<Page<Conclusion>>(`/cases/${c.id}/conclusions`, { params: { offset, limit: 10 }, signal: controller.signal })).data
      if (controller.signal.aborted) return
      setItems(page.items); setTotal(page.total)
    } catch (e) { if (controller.signal.aborted) return; setItems([]); setPreview(null); setError(caseError(e)) }
  }, [c.id, offset])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, c.version])
  async function mutate(path: string, payload: unknown) {
    setBusy(true); setError('')
    try { await api.post(`/cases/${c.id}/${path}`, payload); await onChange(); await load(); return true }
    catch (e) { setError(caseError(e)); await onChange(); return false }
    finally { setBusy(false) }
  }
  return <section id="conclusion" className={cardClass}>
    <h2 className="text-lg font-semibold">Итог разбора</h2>
    <p className="text-sm text-gray-500">Автор итога — координатор. Участие коллег не обозначает согласия с выводами.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!items.length && <p>Итог пока не сохранён.</p>}
    {items.map(item => <article key={item.id} className="space-y-2 rounded-lg bg-gray-50 p-4">
      <p className="text-sm text-gray-500">Версия {item.number} · координатор · {new Date(item.created_at).toLocaleString('ru-RU')}</p>
      <h3 className="font-medium">Резюме</h3><p className="whitespace-pre-wrap">{item.summary}</p>
      <h3 className="font-medium">Выводы</h3><p className="whitespace-pre-wrap">{item.findings}</p>
      <h3 className="font-medium">Дальнейшие действия</h3><p className="whitespace-pre-wrap">{item.next_actions}</p>
      {item.source_ids.map(id => <button key={id} className="mr-3 text-primary-700 underline" onClick={() => onOpen?.(id)}>Источник {id.slice(0, 8)}</button>)}
    </article>)}
    <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 10)}>Новые версии</button>
      <span>{total} версий</span><button disabled={offset + 10 >= total} onClick={() => setOffset(offset + 10)}>Ранее</button></div>
    {owner && c.status !== 'closed' && <>
      <button className={buttonClass} onClick={() => {
        const current = offset === 0 ? items[0] : undefined
        setSummary(current?.summary ?? ''); setFindings(current?.findings ?? ''); setActions(current?.next_actions ?? '')
        setSources(current?.source_ids ?? []); setEdit(true)
      }}>Составить новую версию итога</button>
      {edit && <div className="space-y-3">
        <label>Краткое резюме<textarea className={inputClass} maxLength={10000} value={summary} onChange={e => setSummary(e.target.value)} /></label>
        <label>Выводы<textarea className={inputClass} maxLength={10000} value={findings} onChange={e => setFindings(e.target.value)} /></label>
        <label>Дальнейшие действия<textarea className={inputClass} maxLength={10000} value={actions} onChange={e => setActions(e.target.value)} /></label>
        <CaseMaterialPicker caseId={c.id} sequence={c.sequence} selected={sources} multiple
          onChange={setSources} onAccessLost={onChange} />
        <button className={buttonClass} disabled={busy || !summary.trim()} onClick={async () => {
          if (await mutate('conclusions', { version: c.version, summary, findings, next_actions: actions, source_ids: sources })) setEdit(false)
        }}>Сохранить версию итога</button><button onClick={() => setEdit(false)}>Отмена</button>
      </div>}
      <button className="ml-4 text-primary-700" disabled={busy || total === 0} onClick={async () => {
        try { const result = (await api.get<{ open_requests: number }>(`/cases/${c.id}/closure-preview`)).data
          setOpenRequests(result.open_requests); setCancelRequests(false)
        } catch (e) { setError(caseError(e)) }
      }}>Завершить разбор</button>
      {openRequests !== null && <div role="dialog" aria-label="Завершение разбора" className="rounded-lg border p-4 space-y-3">
        <p>Открытых запросов: {openRequests}. После завершения материалы, обсуждение и итог доступны только для чтения.</p>
        {openRequests > 0 && <label className="block"><input type="checkbox" checked={cancelRequests} onChange={e => setCancelRequests(e.target.checked)} /> Отменить незавершённые запросы при закрытии</label>}
        <button className={buttonClass} disabled={busy || (openRequests > 0 && !cancelRequests)} onClick={async () => {
          if (await mutate('close', { version: c.version, cancel_open_requests: cancelRequests })) setOpenRequests(null)
        }}>Подтвердить завершение</button><button onClick={() => setOpenRequests(null)}>Продолжить обсуждение</button>
      </div>}
    </>}
    {owner && c.status === 'closed' && <>
      {c.published_record_id ? <div><p>Итог опубликован как самостоятельная запись. Доступ коллегам передаётся через раздел «Доступ к записям».</p>
        <Link className="text-primary-700 underline" to={`/patients/${c.patient_id}`}>Открыть историю пациента</Link></div> :
        <button className={buttonClass} onClick={async () => {
          try { setPreview((await api.get<Preview>(`/cases/${c.id}/publication-preview`)).data) }
          catch (e) { setError(caseError(e)) }
        }}>Предпросмотр публикации в истории</button>}
      {preview && !c.published_record_id && <div role="dialog" aria-label="Публикация итога" className="rounded-lg border p-4 space-y-3">
        <h3 className="font-semibold">{preview.title}</h3><p className="whitespace-pre-wrap">{preview.clinical_summary}</p>
        <p>Версия итога: {preview.conclusion_version}. Запись не подтверждается автоматически.</p>
        <label className="block">Дата медицинского события<input className={inputClass} type="date" value={eventDate} onChange={e => setEventDate(e.target.value)} /></label>
        <button className={buttonClass} disabled={busy || !eventDate} onClick={async () => {
          if (await mutate('publish', { event_date: eventDate })) setPreview(null)
        }}>Опубликовать в истории</button><button onClick={() => setPreview(null)}>Отмена</button>
      </div>}
    </>}
  </section>
}
