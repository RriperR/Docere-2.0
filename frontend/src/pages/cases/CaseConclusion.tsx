import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Modal from '../../components/common/Modal'
import CaseMaterialPicker from './CaseMaterialPicker'
import DraftStatus from './DraftStatus'
import { emptyWorkDraft, useCaseWorkDraft } from '../../hooks/useCaseWorkDraft'
import api from '../../api/api'
import { caseError, type ClinicalCase, type Page } from '../../api/cases'
import { buttonClass, cardClass, inputClass } from './styles'

interface Conclusion { id: string; number: number; author_id: string; summary: string; findings: string; next_actions: string; source_ids: string[]; created_at: string; sources: { id: string; title: string | null; event_date: string }[] }
interface Preview { title: string; clinical_summary: string; conclusion_version: number; published_record_id: string | null }

export default function CaseConclusion({ c, owner, onChange, onOpen }: {
  c: ClinicalCase; owner: boolean; onChange: () => Promise<void>; onOpen?: (id: string) => void
}) {
  const formId = useId()
  const [items, setItems] = useState<Conclusion[]>([])
  const [offset, setOffset] = useState(0)
  const [history, setHistory] = useState(false)
  const [latest, setLatest] = useState<Conclusion | null>(null)
  const [closureVersion, setClosureVersion] = useState(c.version)
  const [useSaved, setUseSaved] = useState(false)
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
  const draft = useCaseWorkDraft(c.id, 'conclusion', owner && c.status !== 'closed', {
    ...emptyWorkDraft, text: summary, findings, next_actions: actions, record_ids: sources,
  }, value => {
    setSummary(value.text); setFindings(value.findings); setActions(value.next_actions); setSources(value.record_ids)
    if (value.text || value.findings || value.next_actions) setEdit(true)
  }, busy)
  const activeRead = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    try { const page = (await api.get<Page<Conclusion>>(`/cases/${c.id}/conclusions`, { params: { offset: history ? offset : 0, limit: history ? 10 : 1 }, signal: controller.signal })).data
      if (controller.signal.aborted) return
      setItems(page.items); setTotal(page.total); if (!history || offset === 0) setLatest(page.items[0] ?? null)
    } catch (e) { if (controller.signal.aborted) return; setItems([]); setPreview(null); setError(caseError(e)) }
  }, [c.id, offset, history])
  useEffect(() => { void load(); return () => activeRead.current?.abort() }, [load, c.version])
  async function mutate(path: string, payload: unknown) {
    setBusy(true); setError('')
    try { await api.post(`/cases/${c.id}/${path}`, payload); await onChange(); await load(); return true }
    catch (e) { setError(caseError(e)); await onChange(); return false }
    finally { setBusy(false) }
  }
  const hasDraft = !!(summary || findings || actions || sources.length)
  const draftDiffers = hasDraft && (!latest || summary !== latest.summary || findings !== latest.findings || actions !== latest.next_actions || JSON.stringify([...sources].sort()) !== JSON.stringify([...latest.source_ids].sort()))
  async function previewClosure() {
    try { const result = (await api.get<{ open_requests: number; version: number }>(`/cases/${c.id}/closure-preview`)).data
      setOpenRequests(result.open_requests); setClosureVersion(result.version); setCancelRequests(false); setUseSaved(false)
    } catch (e) { setError(caseError(e)) }
  }
  async function save() {
    if (!await draft.flush()) return false
    if (!await mutate('conclusions', { version: c.version, summary, findings, next_actions: actions, source_ids: sources })) return false
    await draft.refresh(); setEdit(false); return true
  }
  return <section id="conclusion" className={cardClass}>
    <ol aria-label="Этапы завершения" className="mb-4 flex flex-wrap gap-3 text-sm"><li className="rounded-lg bg-primary-50 px-3 py-2">1. Сохранить итог</li><li className="rounded-lg bg-primary-50 px-3 py-2">2. Завершить разбор</li><li className="rounded-lg bg-primary-50 px-3 py-2">3. Опубликовать в истории</li></ol>
    <h2 className="text-lg font-semibold">Итог разбора</h2>
    <p className="text-sm text-gray-500">Автор итога — координатор. Участие коллег не обозначает согласия с выводами.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!items.length && <p>Итог пока не сохранён.</p>}
    {items.map(item => <article key={item.id} className="space-y-2 rounded-lg bg-gray-50 p-4">
      <p className="text-sm text-gray-500">Версия {item.number} · координатор · {new Date(item.created_at).toLocaleString('ru-RU')}</p>
      <h3 className="font-medium">Резюме</h3><p className="whitespace-pre-wrap">{item.summary}</p>
      <h3 className="font-medium">Выводы</h3><p className="whitespace-pre-wrap">{item.findings}</p>
      <h3 className="font-medium">Дальнейшие действия</h3><p className="whitespace-pre-wrap">{item.next_actions}</p>
      {item.sources.map(source => <button key={source.id} className="mr-3 text-primary-700 underline" onClick={() => onOpen?.(source.id)}>{source.title ?? 'Медицинская запись'} · {source.event_date}</button>)}
    </article>)}
    <button className="text-primary-700 underline" onClick={() => { setHistory(value => !value); setOffset(0) }}>{history ? 'Скрыть предыдущие версии' : `Предыдущие версии (${Math.max(0, total - 1)})`}</button>
    {history && <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 10)}>Новые версии</button>
      <span>{total} версий</span><button disabled={offset + 10 >= total} onClick={() => setOffset(offset + 10)}>Ранее</button></div>}
    {owner && c.status !== 'closed' && <>
      <button className={buttonClass} disabled={!draft.ready} onClick={() => {
        if (summary || findings || actions) { setEdit(true); return }
        const current = offset === 0 ? items[0] : undefined
        setSummary(current?.summary ?? ''); setFindings(current?.findings ?? ''); setActions(current?.next_actions ?? '')
        setSources(current?.source_ids ?? []); setEdit(true)
      }}>Составить новую версию итога</button>
      {edit && <div className="space-y-3">
        <p className="text-sm text-gray-500">Личный черновик — ещё не сохранённая версия итога.</p>
        <label htmlFor={`${formId}-summary`}>Краткое резюме</label><textarea id={`${formId}-summary`} className={inputClass} maxLength={10000} value={summary} onChange={e => setSummary(e.target.value)} />
        <label htmlFor={`${formId}-findings`}>Выводы</label><textarea id={`${formId}-findings`} className={inputClass} maxLength={10000} value={findings} onChange={e => setFindings(e.target.value)} />
        <label htmlFor={`${formId}-actions`}>Дальнейшие действия</label><textarea id={`${formId}-actions`} className={inputClass} maxLength={10000} value={actions} onChange={e => setActions(e.target.value)} />
        <CaseMaterialPicker caseId={c.id} sequence={c.sequence} selected={sources} multiple
          onChange={setSources} onAccessLost={onChange} />
        <button className={buttonClass} disabled={busy || !summary.trim() || !draft.ready || draft.conflict} onClick={async () => {
          await save()
        }}>Сохранить версию итога</button><button onClick={() => setEdit(false)}>Свернуть редактор</button>
        <DraftStatus draft={draft} />
      </div>}
      <button className="ml-4 text-primary-700" disabled={busy || total === 0} onClick={() => void previewClosure()}>Завершить разбор</button>
      {openRequests !== null && <Modal title="Завершение разбора" onClose={() => setOpenRequests(null)}><div className="space-y-3 p-4">
        <h3 className="text-lg font-semibold">Завершить с версией {latest?.number}</h3>
        {draftDiffers && <div className="rounded-xl bg-warning-50 p-4"><p>Личный черновик отличается от сохранённого итога. Выберите, что зафиксировать.</p><button className={buttonClass} disabled={busy || !summary.trim() || draft.conflict} onClick={async () => { if (await save()) { setOpenRequests(null); await previewClosure() } }}>Сохранить черновик новой версией</button><label className="mt-3 block"><input type="checkbox" checked={useSaved} onChange={e => setUseSaved(e.target.checked)} /> Завершить с сохранённой версией; личный черновик не включать</label></div>}
        <p>Открытых запросов: {openRequests}. После завершения материалы, обсуждение и итог доступны только для чтения.</p>
        {openRequests > 0 && <label className="block"><input type="checkbox" checked={cancelRequests} onChange={e => setCancelRequests(e.target.checked)} /> Отменить незавершённые запросы при закрытии</label>}
        <button className={buttonClass} disabled={busy || (openRequests > 0 && !cancelRequests) || (draftDiffers && !useSaved)} onClick={async () => {
          if (await mutate('close', { version: closureVersion, cancel_open_requests: cancelRequests })) setOpenRequests(null)
        }}>Подтвердить завершение</button><button onClick={() => setOpenRequests(null)}>Продолжить обсуждение</button>
      </div></Modal>}
    </>}
    {owner && c.status === 'closed' && <>
      {c.published_record_id ? <div><p>Итог опубликован как самостоятельная запись. Доступ коллегам передаётся через раздел «Доступ к записям».</p>
        <Link className="text-primary-700 underline" to={`/patients/${c.patient_id}?record=${c.published_record_id}`}>Открыть историю пациента</Link></div> :
        <button className={buttonClass} onClick={async () => {
          try { setPreview((await api.get<Preview>(`/cases/${c.id}/publication-preview`)).data) }
          catch (e) { setError(caseError(e)) }
        }}>Предпросмотр публикации в истории</button>}
      {preview && !c.published_record_id && <Modal title="Публикация итога" onClose={() => setPreview(null)}><div className="space-y-3 p-4">
        <h3 className="font-semibold">{preview.title}</h3><p className="whitespace-pre-wrap">{preview.clinical_summary}</p>
        <p>Версия итога: {preview.conclusion_version}. Запись не подтверждается автоматически.</p>
        <label className="block">Дата медицинского события<input className={inputClass} type="date" value={eventDate} onChange={e => setEventDate(e.target.value)} /></label>
        <button className={buttonClass} disabled={busy || !eventDate} onClick={async () => {
          if (await mutate('publish', { event_date: eventDate })) setPreview(null)
        }}>Опубликовать в истории</button><button onClick={() => setPreview(null)}>Отмена</button>
      </div></Modal>}
    </>}
  </section>
}
