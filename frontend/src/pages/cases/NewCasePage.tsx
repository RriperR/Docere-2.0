import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { caseApi, caseError, type Material, type PatientOption } from '../../api/cases'
import { buttonClass, cardClass, inputClass } from './CasesPage'

export default function NewCasePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [patientId, setPatientId] = useState(params.get('patient') ?? '')
  const [patientQuery, setPatientQuery] = useState('')
  const [patients, setPatients] = useState<PatientOption[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!patientId) return
    let cancelled = false
    void caseApi.available(patientId, '', offset).then(page => {
      if (!cancelled) { setMaterials(page.items); setTotal(page.total) }
    }).catch(e => { if (!cancelled) setError(caseError(e)) })
    return () => { cancelled = true }
  }, [patientId, offset])
  async function searchPatients() {
    try { setPatients(await caseApi.patients(patientQuery)); setError('') }
    catch (e) { setError(caseError(e)) }
  }
  async function create() {
    setBusy(true); setError('')
    try {
      const view = await caseApi.create({ patient_id: patientId, title, question, record_ids: selected,
        previous_case_id: params.get('previous') })
      navigate(`/cases/${view.id}`)
    } catch (e) { setError(caseError(e)) } finally { setBusy(false) }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold">Создать клинический случай</h1>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <section className={cardClass}>
      <label className="block">Найти пациента
        <input className={inputClass} value={patientQuery} onChange={e => setPatientQuery(e.target.value)} /></label>
      <button disabled={patientQuery.length < 2} onClick={() => void searchPatients()}>Найти</button>
      {patients.map(p => <button key={p.id} className="block text-primary-700" onClick={() => {
        setPatientId(p.id); setPatientQuery(p.fio); setSelected([]); setOffset(0); setPatients([])
      }}>{p.fio} · {p.id.slice(0, 8)}</button>)}
      {patientId && <p>Выбран паспорт пациента: {patientId}</p>}
      <label className="block">Название<input className={inputClass} maxLength={255} value={title}
        onChange={e => setTitle(e.target.value)} /></label>
      <label className="block">Вопрос для обсуждения<textarea className={inputClass} maxLength={10000} value={question}
        onChange={e => setQuestion(e.target.value)} /></label>
      <h2 className="font-semibold">Выберите доступные материалы одного пациента</h2>
      {materials.map(m => <label key={m.id} className="block"><input type="checkbox" checked={selected.includes(m.id)}
        onChange={e => setSelected(e.target.checked ? [...selected, m.id] : selected.filter(id => id !== m.id))} />
        {' '}{m.event_date} · {m.title ?? m.record_type}</label>)}
      <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Назад</button>
        <span>{selected.length} выбрано · {total} доступно</span>
        <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Далее</button></div>
      <button className={buttonClass} disabled={busy || !patientId || !title.trim() || !question.trim()}
        onClick={() => void create()}>Создать черновик</button>
    </section>
  </div>
}
