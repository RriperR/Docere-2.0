import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { caseApi, caseError, type CaseView, type Doctor } from '../../api/cases'
import { watchChanges } from '../../api/caseUpdates'
import CaseMaterials from './CaseMaterials'
import CaseDocumentPanel, { type MaterialReference } from './CaseDocumentPanel'
import CaseConclusion from './CaseConclusion'
import CaseDiscussion from './CaseDiscussion'
import { useAuthStore } from '../../stores/authStore'
import { buttonClass, cardClass, inputClass, stateLabel, stateTone, memberLabel } from './styles'

export default function CasePage() {
  const { id = '' } = useParams()
  return <CaseWorkspace key={id} id={id} />
}

function CaseWorkspace({ id }: { id: string }) {
  const userId = useAuthStore(s => s.user?.id)
  const [view, setView] = useState<CaseView | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [params, setParams] = useSearchParams()
  const section = ['review', 'conclusion', 'members'].includes(params.get('tab') ?? '') ? params.get('tab')! : 'review'
  const setSection = (value: string) => setParams(previous => { const next = new URLSearchParams(previous); next.set('tab', value); return next })
  const [mobilePane, setMobilePane] = useState('materials')
  const [query, setQuery] = useState('')
  const recordId = params.get('record')
  const document = recordId ? { recordId, attachmentId: params.get('attachment') } : null
  const setDocument = useCallback((value: { recordId: string; attachmentId: string | null } | null) => setParams(previous => { const next = new URLSearchParams(previous); next.delete('record'); next.delete('attachment'); if (value) { next.set('record', value.recordId); if (value.attachmentId) next.set('attachment', value.attachmentId) }; return next }), [setParams])
  const [reference, setReference] = useState<MaterialReference | null>(null)
  const openMaterial = useCallback((recordId: string, attachmentId: string | null = null) => {
    setParams(previous => { const next = new URLSearchParams(previous); next.set('tab', 'review'); next.set('record', recordId); next.delete('attachment'); if (attachmentId) next.set('attachment', attachmentId); return next }); setMobilePane('materials')
  }, [setParams])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const reads = useRef(0)
  const load = useCallback(async () => {
    const request = ++reads.current
    try { const next = await caseApi.get(id); if (request === reads.current) setView(next) }
    catch (e) { if (request === reads.current) { setView(null); setError(caseError(e)) } }
  }, [id])
  useEffect(() => { setView(null); void load(); return () => { reads.current += 1 } }, [load])
  const accessible = !!view?.accessible
  useEffect(() => {
    if (view && !accessible) { setDocument(null); setReference(null) }
  }, [accessible, view, setDocument])
  useEffect(() => {
    if (!accessible) return
    const controller = new AbortController()
    void watchChanges(`/cases/${id}/events`, controller.signal, load, load)
    return () => controller.abort()
  }, [id, accessible, load])
  async function action(path: string, payload?: unknown) {
    setBusy(true); setError('')
    try { setView(await caseApi.post(id, path, payload)) }
    catch (e) { setError(caseError(e)); await load() }
    finally { setBusy(false) }
  }
  async function searchDoctors() {
    try { setDoctors(await caseApi.doctors(query)) } catch (e) { setError(caseError(e)) }
  }
  const c = view?.case
  const owner = view?.coordinator_id === userId
  return <div className="space-y-5">
    <Link to="/cases">← Клинические случаи</Link>
    {error && <p role="alert" className="text-red-700">{error} <button onClick={() => void load()}>Обновить данные</button></p>}
    {!view && !error && <p role="status" className="text-sm text-gray-500">Загружаем клинический случай…</p>}
    {view && !c && <section className={cardClass}>
      <h1 className="text-xl font-bold">{view.membership_status === 'pending' ? 'Приглашение в разбор' : 'Клинический контекст недоступен'}</h1>
      <p>Координатор: {view.coordinator_name} · {view.material_count} материалов</p>
      {view.membership_status === 'pending' && <><p>{view.invitation_terms}</p>
        <button className={buttonClass} disabled={busy} onClick={() => void action('invitations/accept')}>Принять приглашение</button>
        <button disabled={busy} onClick={() => void action('invitations/decline')}>Отклонить</button></>}
      {owner && view.management_members.map(m => ['pending', 'accepted'].includes(m.status) && <div key={m.user_id}>
        <span>{m.name} · {memberLabel[m.status] ?? 'Участник'}</span> <button disabled={busy}
          onClick={() => void action(`members/${m.user_id}/${m.status === 'pending' ? 'cancel' : 'remove'}`)}>
          {m.status === 'pending' ? 'Отозвать приглашение' : 'Исключить'}</button>
      </div>)}
      {view.membership_status === 'accepted' && <button disabled={busy} onClick={() => void action('leave')}>Выйти из случая</button>}
    </section>}
    {c && <>
      <section className={cardClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stateTone[c.status]}`}>{stateLabel[c.status]}</span>
          <span className="text-sm text-gray-500">Координатор: {view.coordinator_name}</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{c.title}</h1>
        <p className="text-sm text-gray-500">Пациент: {view.patient_name}</p>
        <div className="rounded-xl border-l-4 border-primary-500 bg-primary-50/60 p-4">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-primary-700">Вопрос для коллег</p><p className="whitespace-pre-wrap leading-relaxed">{c.question}</p>
        </div>
        {c.previous_case_id && <Link to={`/cases/${c.previous_case_id}`}>Предыдущий случай (доступ проверяется отдельно)</Link>}
        {c.status === 'closed' && <Link to={`/cases/new?patient=${c.patient_id}&previous=${c.id}`}>Создать продолжение</Link>}
      </section>
      <nav aria-label="Разделы клинического случая" className="sticky top-14 z-10 flex flex-wrap gap-2 rounded-xl border border-gray-200 bg-white/95 p-2 shadow-xs backdrop-blur-sm">
        {[['review', 'Совместный разбор'], ['conclusion', 'Итог'], ['members', 'Участники']].map(([value, label]) =>
          <button key={value} type="button" aria-pressed={section === value} onClick={() => setSection(value)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${section === value ? 'bg-primary-50 text-primary-700' : 'text-gray-500 hover:bg-gray-50'}`}>{label}</button>)}
      </nav>
      <div hidden={section !== 'members'}>
      <section id="members" className={cardClass}><h2 className="text-lg font-semibold">Участники</h2>
        {c.members.map(m => <div key={m.user_id} className="flex gap-4">
          <span>{m.name} · {memberLabel[m.status] ?? 'Участник'}</span>
          {owner && ['pending', 'accepted'].includes(m.status) && <button disabled={busy}
            onClick={() => void action(`members/${m.user_id}/${m.status === 'pending' ? 'cancel' : 'remove'}`)}>
            {m.status === 'pending' ? 'Отозвать приглашение' : 'Исключить'}</button>}
        </div>)}
        {!owner && <button disabled={busy} onClick={() => void action('leave')}>Выйти из случая</button>}
        {owner && c.status !== 'closed' && <div className="space-y-2">
          <label>Найти врача<input className={inputClass} value={query} onChange={e => setQuery(e.target.value)} /></label>
          <button disabled={query.length < 2} onClick={() => void searchDoctors()}>Найти врача</button>
          {doctors.map(d => <button className="block text-primary-700" key={d.id} disabled={busy}
            onClick={() => void action('invitations', { user_id: d.id, version: c.version })}>Пригласить: {d.name} ({d.email})</button>)}
        </div>}
      </section>
      </div>
      <div hidden={section !== 'review'}>
        <div className="mb-4 flex gap-2 lg:hidden" role="group" aria-label="Панели разбора">
          {[['materials', 'Материалы'], ['discussion', 'Обсуждение']].map(([value, label]) =>
            <button key={value} className={`flex-1 rounded-xl border px-4 py-2 text-sm font-semibold ${mobilePane === value ? 'border-primary-200 bg-primary-50 text-primary-700' : 'border-gray-200 bg-white text-gray-600'}`}
              aria-pressed={mobilePane === value} onClick={() => setMobilePane(value)}>{label}</button>)}
        </div>
        <div className="grid items-start gap-5 lg:grid-cols-2">
          <div className={`min-w-0 space-y-4 lg:sticky lg:top-32 lg:max-h-[calc(100vh-9rem)] lg:overflow-y-auto ${mobilePane !== 'materials' ? 'hidden lg:block' : ''}`}>
            {document && <CaseDocumentPanel key={`${id}-${document.recordId}`} caseId={id} recordId={document.recordId}
              attachmentId={document.attachmentId} onClose={() => setDocument(null)} onAccessLost={load}
              onReference={ref => { setReference(ref); setMobilePane('discussion') }} />}
            <CaseMaterials c={c} owner={owner} onChange={load} onOpen={openMaterial} />
          </div>
          <div className={`min-w-0 space-y-5 ${mobilePane !== 'discussion' ? 'hidden lg:block' : ''}`}>
            <CaseDiscussion c={c} userId={userId ?? ''} onChange={load} onOpen={openMaterial} reference={reference} />
          </div>
        </div>
      </div>
      <div hidden={section !== 'conclusion'}><CaseConclusion c={c} owner={owner} onChange={load} onOpen={openMaterial} /></div>
    </>}
  </div>
}
