import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { caseApi, caseError, type CaseView, type Doctor } from '../../api/cases'
import { watchChanges } from '../../api/caseUpdates'
import CaseMaterials from './CaseMaterials'
import CaseDocumentPanel, { type MaterialReference } from './CaseDocumentPanel'
import CaseConclusion from './CaseConclusion'
import CaseDiscussion from './CaseDiscussion'
import { useAuthStore } from '../../stores/authStore'
import { buttonClass, cardClass, inputClass, stateLabel } from './styles'

export default function CasePage() {
  const { id = '' } = useParams()
  const userId = useAuthStore(s => s.user?.id)
  const [view, setView] = useState<CaseView | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [document, setDocument] = useState<{ recordId: string; attachmentId: string | null } | null>(null)
  const [reference, setReference] = useState<MaterialReference | null>(null)
  const openMaterial = useCallback((recordId: string, attachmentId: string | null = null) => {
    setDocument({ recordId, attachmentId })
  }, [])
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
    {view && !c && <section className={cardClass}>
      <h1 className="text-xl font-bold">{view.membership_status === 'pending' ? 'Приглашение в разбор' : 'Клинический контекст недоступен'}</h1>
      <p>Координатор: {view.coordinator_name} · {view.material_count} материалов</p>
      {view.membership_status === 'pending' && <><p>{view.invitation_terms}</p>
        <button className={buttonClass} disabled={busy} onClick={() => void action('invitations/accept')}>Принять приглашение</button>
        <button disabled={busy} onClick={() => void action('invitations/decline')}>Отклонить</button></>}
      {owner && view.management_members.map(m => ['pending', 'accepted'].includes(m.status) && <div key={m.user_id}>
        <span>{m.name} · {m.status}</span> <button disabled={busy}
          onClick={() => void action(`members/${m.user_id}/${m.status === 'pending' ? 'cancel' : 'remove'}`)}>
          {m.status === 'pending' ? 'Отозвать приглашение' : 'Исключить'}</button>
      </div>)}
      {view.membership_status === 'accepted' && <button disabled={busy} onClick={() => void action('leave')}>Выйти из случая</button>}
    </section>}
    {c && <>
      <section className={cardClass}>
        <h1 className="text-2xl font-bold">{c.title}</h1><p>Пациент: {view.patient_name}</p><p>{c.question}</p>
        <p>{stateLabel[c.status]} · Координатор: {view.coordinator_name} · версия {c.version}</p>
        <p>Участие врача не означает согласия с выводами.</p>
        {c.previous_case_id && <Link to={`/cases/${c.previous_case_id}`}>Предыдущий случай (доступ проверяется отдельно)</Link>}
        {c.status === 'closed' && <Link to={`/cases/new?patient=${c.patient_id}&previous=${c.id}`}>Создать продолжение</Link>}
      </section>
      <section className={cardClass}><h2 className="font-semibold">Участники</h2>
        {c.members.map(m => <div key={m.user_id} className="flex gap-4">
          <span>{m.name} · {m.status}</span>
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
      <CaseMaterials c={c} owner={owner} onChange={load} onOpen={openMaterial} />
      <CaseDiscussion c={c} userId={userId ?? ''} onChange={load} onOpen={openMaterial} reference={reference} />
      <CaseConclusion c={c} owner={owner} onChange={load} onOpen={openMaterial} />
      {document && <CaseDocumentPanel key={`${id}-${document.recordId}`} caseId={id} recordId={document.recordId}
        attachmentId={document.attachmentId} onClose={() => setDocument(null)} onAccessLost={load}
        onReference={ref => { setReference(ref); setDocument(null) }} />}
    </>}
  </div>
}
