import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { caseApi, caseError, type CaseView, type Doctor } from '../../api/cases'
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
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const load = useCallback(async () => {
    try { setView(await caseApi.get(id)) } catch (e) { setView(null); setError(caseError(e)) }
  }, [id])
  useEffect(() => { void load() }, [load])
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
      {view.membership_status === 'accepted' && <button disabled={busy} onClick={() => void action('leave')}>Выйти из случая</button>}
    </section>}
    {c && <>
      <section className={cardClass}>
        <h1 className="text-2xl font-bold">{c.title}</h1><p>{c.question}</p>
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
      <section className={cardClass}><h2 className="font-semibold">Материалы</h2>
        <p>{c.record_ids.length} выбранных записей. Доступ к остальной истории пациента не предоставляется.</p>
      </section>
      <CaseDiscussion c={c} userId={userId ?? ''} onChange={load} />
    </>}
  </div>
}
