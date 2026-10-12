import axios from 'axios'
import { useCallback, useEffect, useRef, useState } from 'react'
import { caseAiApi, type CaseSummaryRun, type SummaryCapabilities } from '../../api/caseAi'
import { caseError, type ClinicalCase, type Material } from '../../api/cases'
import { buttonClass, cardClass } from './styles'

const active = (run: CaseSummaryRun | null) => !!run && ['queued', 'running'].includes(run.status)
const statusLabel: Record<string, string> = { queued: 'Ожидает обработки', running: 'Анализируем документы', completed: 'Сводка готова', completed_with_errors: 'Сводка готова частично', failed: 'Не удалось подготовить сводку', cancelled: 'Анализ отменён' }
const errorLabel: Record<string, string> = {
  unsupported_document: 'Этот формат не отправлялся AI. Откройте материал вручную.', no_documents: 'У записи нет исходных документов.',
  unreadable_document: 'Документ не удалось прочитать. Проверьте файл или защиту паролем.', multiple_patients_document: 'В документе обнаружены разные пациенты. Факты скрыты; проверьте оригинал.',
  document_page_limit: 'Превышен лимит страниц документа. Полный анализ не выполнен.', page_limit: 'Превышен общий лимит страниц. Полный анализ не выполнен.',
  provider_authentication: 'Проверьте серверную настройку доступа к AI.', provider_unavailable: 'AI-сервис временно недоступен.',
  invalid_response: 'Ответ AI не прошёл проверку. Изучите оригинал.', configuration_changed: 'Настройка AI изменилась. Запустите анализ заново.',
  cancelled: 'Этот документ не был обработан: анализ отменён.', document_size_limit: 'Размер документа превышает 30 МБ.',
}
const issueLabel = (issue: string) => issue === 'conflicting:event_date' ? 'Несколько дат: основная дата события не выбрана.' : issue

export default function CaseAiSummary({ c, onOpen, onAccessLost }: {
  c: ClinicalCase; onOpen: (record: string, attachment: string | null, page: number) => void; onAccessLost: () => Promise<void>
}) {
  const [caps, setCaps] = useState<SummaryCapabilities | null>(null)
  const [materials, setMaterials] = useState<Material[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [selection, setSelection] = useState<string[]>([])
  const [consent, setConsent] = useState(false)
  const [run, setRun] = useState<CaseSummaryRun | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const pendingKey = useRef<string | null>(null)
  const reads = useRef<AbortController | null>(null)
  const mutation = useRef<AbortController | null>(null)
  useEffect(() => () => { reads.current?.abort(); mutation.current?.abort() }, [])
  const refresh = useCallback(async (clear = false) => {
    reads.current?.abort()
    const controller = new AbortController(); reads.current = controller
    if (clear) { setRun(null); setMaterials([]); setLoading(true) }
    try {
      const [configuration, page, latest] = await Promise.all([
        caseAiApi.capabilities(controller.signal), caseAiApi.materials(c.id, offset, controller.signal), caseAiApi.latest(c.id, controller.signal).then(value => ({ value, stale: '' })).catch(e => {
          if (axios.isAxiosError(e) && e.response?.status === 409) return { value: null, stale: caseError(e) }
          throw e
        }),
      ])
      if (controller.signal.aborted) return
      setCaps(configuration); setMaterials(page.items); setTotal(page.total); setRun(latest.value); setError(latest.stale)
    } catch (e) {
      if (controller.signal.aborted) return
      setRun(null); setError(caseError(e)); setMaterials([]); await onAccessLost()
    } finally { if (!controller.signal.aborted) setLoading(false) }
  }, [c.id, offset, onAccessLost])
  const recordKeys = c.record_ids.join(',')
  useEffect(() => { setSelection(previous => previous.filter(id => recordKeys.split(',').includes(id))); void refresh(true) }, [refresh, c.sequence, recordKeys])
  useEffect(() => {
    const focus = () => { if (!document.hidden && !busy) void refresh(true) }
    window.addEventListener('focus', focus); document.addEventListener('visibilitychange', focus)
    const timer = window.setInterval(() => { if (!document.hidden && active(run) && !busy) void refresh() }, 3000)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', focus); document.removeEventListener('visibilitychange', focus) }
  }, [refresh, run, busy])
  async function start() {
    reads.current?.abort(); setBusy(true); setError('')
    const controller = new AbortController(); mutation.current = controller
    pendingKey.current ??= crypto.randomUUID()
    try {
      const next = await caseAiApi.start(c.id, selection, c.version, pendingKey.current, controller.signal)
      if (!controller.signal.aborted) { setRun(next); pendingKey.current = null }
    } catch (e) { if (!controller.signal.aborted) { setRun(null); setError(caseError(e)); await onAccessLost() } }
    finally { if (!controller.signal.aborted) { setBusy(false); setLoading(false) } }
  }
  async function cancel() {
    if (!run) return
    reads.current?.abort(); setBusy(true); setError('')
    const controller = new AbortController(); mutation.current = controller
    try {
      const next = await caseAiApi.cancel(c.id, run.id, controller.signal)
      if (!controller.signal.aborted) setRun(next)
    } catch (e) { if (!controller.signal.aborted) { setRun(null); setError(caseError(e)); await onAccessLost() } }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  const documents = [...(run?.documents ?? [])].sort((a, b) => a.record_date.localeCompare(b.record_date) || a.title.localeCompare(b.title) || a.filename.localeCompare(b.filename))
  return <section className={`${cardClass} min-w-0`} aria-label="AI-сводка материалов">
    <h2 className="text-xl font-semibold">AI-сводка материалов</h2>
    <p className="text-sm text-gray-600">Хронология и факты из выбранных документов для проверки врачом. Сверьте каждый пункт с оригиналом перед использованием в обсуждении или итоге.</p>
    <p className="text-sm text-gray-500">Сводка видна только вам. Сохранение записей и публикация итога выполняются отдельно.</p>
    {loading && <p role="status">Загружаем материалы и последний анализ…</p>}
    {error && <p role="alert" className="text-red-700">{error} <button className="underline" onClick={() => void refresh(true)}>Повторить загрузку</button></p>}
    {caps && !caps.enabled && <p className="rounded-xl bg-gray-50 p-3">AI-сервис не настроен. Материалы можно изучить в обычном просмотрщике.</p>}
    <fieldset disabled={busy || active(run)} className="space-y-3">
      <legend className="font-semibold">Какие материалы включить</legend>
      {materials.map(material => <label key={material.id} className="flex gap-3 rounded-xl border p-3">
        <input className="mt-1" type="checkbox" checked={selection.includes(material.id)} onChange={e => {
          pendingKey.current = null
          setSelection(previous => e.target.checked ? [...previous, material.id] : previous.filter(id => id !== material.id))
        }} /><span className="min-w-0 break-words">{material.event_date} · {material.title ?? 'Медицинская запись'}</span>
      </label>)}
      <div className="flex flex-wrap gap-4 text-sm"><button disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 20))}>Предыдущие материалы</button>
        <span>{total} материалов · выбрано {selection.length}</span><button disabled={offset + 20 >= total} onClick={() => setOffset(value => value + 20)}>Следующие материалы</button></div>
      {caps && <p className="text-xs text-gray-500">PDF/PNG/JPEG: до {caps.max_documents} документов, {caps.max_pages} страниц всего, {caps.max_pages_per_document} страниц в документе. DICOM и файлы комментариев не анализируются.</p>}
      <label className="flex items-start gap-3 rounded-xl bg-amber-50 p-3 text-sm"><input className="mt-1" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
        <span>Разрешаю отправить документы выбранных записей внешнему сервису {caps?.provider ?? 'AI'} для подготовки сводки.</span></label>
      <button className={buttonClass} disabled={!caps?.enabled || !consent || !selection.length || selection.length > caps.max_documents || loading} onClick={() => void start()}>Подготовить сводку</button>
    </fieldset>
    {run && <div className="space-y-4 border-t pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p role="status" className="font-semibold">{statusLabel[run.status] ?? 'Состояние анализа'} · {run.documents.filter(d => d.status !== 'queued').length}/{run.documents.length}</p>
        {active(run) && <button disabled={busy} onClick={() => void cancel()}>Остановить анализ</button>}</div>
      <p className="text-xs text-gray-500">{run.provider} · {run.model} · {new Date(run.created_at).toLocaleString('ru-RU')}</p>
      {documents.map(doc => <article key={`${doc.record_id}-${doc.attachment_id ?? 'none'}`} className="space-y-3 rounded-xl border p-4">
        <h3 className="break-words font-semibold">{doc.record_date} · {doc.title}</h3>
        <button className="break-words text-sm text-primary-700 underline" onClick={() => onOpen(doc.record_id, doc.attachment_id, 1)}>{doc.filename || 'Открыть запись'}</button>
        <p className="text-xs text-gray-500">Дата в заголовке — дата записи в истории.{doc.document_date && ` Из документа извлечена дата: ${doc.document_date}.`}</p>
        {doc.error_code && <p className="rounded-lg bg-amber-50 p-3 text-sm">{errorLabel[doc.error_code] ?? 'Документ не удалось обработать. Изучите оригинал.'}</p>}
        {doc.status === 'queued' && <p className="text-sm text-gray-500">Ожидает анализа</p>}
        {(['fact', 'mentioned_care'] as const).map(category => {
          const facts = doc.facts.filter(f => f.category === category)
          return facts.length ? <div key={category} className="space-y-2"><h4 className="text-sm font-semibold">{category === 'fact' ? 'Факты из документа' : 'Указанные в документе назначения и планы'}</h4>
            <ul className="space-y-3">{facts.map((fact, index) => <li key={index} className="space-y-1"><p className="whitespace-pre-wrap break-words text-sm">{fact.text}</p>
              {fact.sources.map((source, n) => <button key={n} className="block max-w-full break-words text-left text-xs text-primary-700 underline" onClick={() => onOpen(doc.record_id, doc.attachment_id, source.page)}>
                Стр. {source.page}: «{source.excerpt}»</button>)}</li>)}</ul></div> : null
        })}
        {!!doc.issues.length && <div className="rounded-lg bg-amber-50 p-3 text-sm"><h4 className="font-semibold">Требует сверки</h4><ul className="list-inside list-disc">{doc.issues.map((issue, i) => <li key={i}>{issueLabel(issue)}</li>)}</ul></div>}
      </article>)}
    </div>}
  </section>
}
