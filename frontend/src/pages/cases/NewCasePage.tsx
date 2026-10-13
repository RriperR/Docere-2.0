import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../../api/api'
import { caseApi, caseError, type CaseView, type Doctor, type Material, type PatientOption } from '../../api/cases'
import { useAuthStore } from '../../stores/authStore'
import { useUnsavedWork } from '../../hooks/useUnsavedWork'
import { buttonClass, cardClass, inputClass, recordTypeLabel, secondaryButtonClass } from './styles'

const steps = ['Пациент', 'Материалы', 'Вопрос и коллега']

export default function NewCasePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const userId = useAuthStore(state => state.user?.id)
  const linkedRecords = useRef([...new Set(params.getAll('record'))])
  const initialPatientId = useRef(params.get('patient'))
  const [contextError, setContextError] = useState('')
  const [contextLoading, setContextLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [patientId, setPatientId] = useState(params.get('patient') ?? '')
  const [patient, setPatient] = useState<PatientOption | null>(null)
  const [patientQuery, setPatientQuery] = useState('')
  const [patients, setPatients] = useState<PatientOption[]>([])
  const [searched, setSearched] = useState(false)
  const [materials, setMaterials] = useState<Material[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [materialQuery, setMaterialQuery] = useState('')
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [doctorQuery, setDoctorQuery] = useState('')
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [invitee, setInvitee] = useState<Doctor | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const created = useRef<CaseView | null>(null)
  useUnsavedWork(!created.current && !!(title || question || selected.length))
  useEffect(() => {
    if (!patientId) return
    const controller = new AbortController()
    setPatient(null); setContextError(''); setContextLoading(true); setSelected([])
    void (async () => {
      const { data } = await api.get<PatientOption>(`/patients/${encodeURIComponent(patientId)}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (data.id !== patientId) throw new Error('Карточка недоступна')
      setPatient(data)
      if (patientId === initialPatientId.current && linkedRecords.current.length) {
        if (linkedRecords.current.length > 100) throw new Error('Выберите не более 100 записей')
        const checked = await Promise.allSettled(linkedRecords.current.map(async id => {
          const response = await api.get<{ id: string; patient_passport_id: string | null }>(`/records/${encodeURIComponent(id)}`, { signal: controller.signal })
          if (response.data.id !== id || response.data.patient_passport_id !== patientId) throw new Error('Запись недоступна')
          return id
        }))
        if (controller.signal.aborted) return
        setSelected(checked.flatMap(result => result.status === 'fulfilled' ? [result.value] : []))
        if (checked.some(result => result.status === 'rejected')) setContextError('Часть записей из ссылки недоступна или относится к другой карточке. Проверьте доступные материалы и выберите их явно.')
        linkedRecords.current = []
      }
    })().catch(() => { if (!controller.signal.aborted) setContextError('Не удалось проверить карточку или записи из ссылки. Выберите пациента и доступные материалы заново.') })
      .finally(() => { if (!controller.signal.aborted) setContextLoading(false) })
    return () => controller.abort()
  }, [patientId, userId])
  useEffect(() => {
    if (!patientId) return
    let cancelled = false
    setMaterials([]); setLoading(true); setError('')
    void caseApi.available(patientId, materialQuery, offset).then(page => {
      if (!cancelled) { setMaterials(page.items); setTotal(page.total) }
    }).catch(cause => { if (!cancelled) setError(caseError(cause)) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [patientId, materialQuery, offset])
  async function searchPatients() {
    setBusy(true); setError('')
    try { setPatients(await caseApi.patients(patientQuery)); setSearched(true) }
    catch (cause) { setError(caseError(cause)) } finally { setBusy(false) }
  }
  async function create() {
    setBusy(true); setError('')
    try {
      created.current ??= await caseApi.create({ patient_id: patientId, title, question, record_ids: selected,
        previous_case_id: params.get('previous') })
      if (invitee && created.current.case?.status === 'draft') {
        created.current = await caseApi.post(created.current.id, 'invitations', {
          user_id: invitee.id, version: created.current.case.version,
        })
      }
      navigate(`/cases/${created.current.id}`)
    } catch (cause) {
      setError(created.current ? 'Случай сохранён, но приглашение не отправлено. Откройте случай и пригласите коллегу там.' : caseError(cause))
    } finally { setBusy(false) }
  }
  return <div className="mx-auto max-w-3xl space-y-6">
    <Link className="text-sm text-gray-500" to="/cases">← Клинические случаи</Link>
    <header><p className="text-xs font-semibold uppercase tracking-widest text-primary-700">Новый совместный разбор</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Создать клинический случай</h1>
      <p className="mt-2 text-sm text-gray-500">Клинический случай — обсуждение выбранных записей. Проверьте пациента и материалы, затем сформулируйте вопрос коллеге.</p></header>
    <ol aria-label="Шаги создания случая" className="grid grid-cols-3 gap-2">
      {steps.map((label, index) => <li key={label} aria-current={index === step ? 'step' : undefined}
        className={`rounded-xl border p-3 text-sm ${index === step ? 'border-primary-200 bg-primary-50 font-semibold text-primary-700' : 'border-gray-200 bg-white text-gray-500'}`}>
        <span className="mr-2">{index + 1}.</span>{label}</li>)}
    </ol>
    {contextLoading && <p role="status">Проверяем доступ к карточке и выбранным записям…</p>}
    {contextError && <p role="alert" className="rounded-xl bg-warning-50 p-4 text-sm text-warning-700">{contextError}</p>}
    {error && <p role="alert" className="rounded-xl bg-error-50 p-4 text-sm text-error-700">{error}
      {created.current && <Link className="ml-2 underline" to={`/cases/${created.current.id}`}>Открыть сохранённый случай</Link>}</p>}
    <section className={cardClass}>
      {step === 0 && <>
        <h2 className="text-lg font-semibold">Чьи материалы будем обсуждать?</h2>
        <form className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void searchPatients() }}>
          <label className="min-w-0 flex-1 text-sm">Найти пациента
            <input className={inputClass} placeholder="ФИО пациента" value={patientQuery} onChange={event => setPatientQuery(event.target.value)} /></label>
          <button className={secondaryButtonClass} disabled={busy || patientQuery.trim().length < 2}>Найти</button>
        </form>
        {patients.map(option => <button key={option.id} className="block w-full rounded-xl border border-gray-200 p-4 text-left hover:border-primary-300"
          onClick={() => { if (option.id !== patientId) { setSelected([]); setOffset(0); setMaterialQuery('') }; setPatientId(option.id); setPatient(option); setPatients([]) }}>
          <span className="font-semibold">{option.fio}</span><span className="mt-1 block text-xs text-gray-500">{option.date_of_birth ? `Дата рождения: ${new Date(option.date_of_birth).toLocaleDateString('ru-RU')}` : 'Дата рождения не указана'}</span>
        </button>)}
        {searched && !patients.length && !patient && <p className="text-sm text-gray-500">Совпадений нет. Проверьте имя или <Link className="underline" to="/patients">добавьте карточку пациента</Link>.</p>}
        {patient && <div className="rounded-xl bg-secondary-50 p-4"><p className="text-xs text-secondary-700">Выбран пациент</p>
          <p className="mt-1 font-semibold">{patient.fio}</p><p className="text-sm text-gray-500">{patient.date_of_birth ? new Date(patient.date_of_birth).toLocaleDateString('ru-RU') : 'Дата рождения не указана'}</p></div>}
        <p className="text-xs text-gray-500">Одинаковые ФИО не объединяют карточки. Выбирайте конкретного пациента.</p>
        <button className={buttonClass} disabled={!patient || busy || contextLoading} onClick={() => setStep(1)}>Перейти к материалам</button>
      </>}
      {step === 1 && <>
        <h2 className="text-lg font-semibold">Материалы · {patient?.fio}</h2>
        <p className="text-sm text-gray-500">Коллега получит доступ только к выбранным записям после принятия приглашения.</p>
        <label className="block text-sm">Поиск материалов<input className={inputClass} maxLength={200} placeholder="Название или описание" value={materialQuery}
          onChange={event => { setMaterialQuery(event.target.value); setOffset(0) }} /></label>
        <p className="text-sm font-semibold text-primary-700">Выбрано: {selected.length} из {total} доступных · максимум 100</p>
        {loading && <p role="status">Загружаем материалы…</p>}
        {!loading && !materials.length && <p className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">{materialQuery ? 'По запросу ничего не найдено.' : 'Доступных записей пока нет. Можно создать черновик и добавить материалы позже.'}</p>}
        {materials.map(material => <label key={material.id} className={`flex items-start gap-3 rounded-xl border p-4 ${selected.includes(material.id) ? 'border-primary-200 bg-primary-50/50' : 'border-gray-200'}`}>
          <input type="checkbox" className="mt-1" checked={selected.includes(material.id)} disabled={!selected.includes(material.id) && selected.length >= 100}
            onChange={event => setSelected(current => event.target.checked ? [...current, material.id] : current.filter(id => id !== material.id))} />
          <span><span className="block text-sm font-semibold">{material.title ?? 'Медицинская запись'}</span><span className="block text-xs text-gray-500">{material.event_date} · {recordTypeLabel[material.record_type]}</span></span>
        </label>)}
        {total > 20 && <div className="flex justify-between gap-3"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Предыдущие материалы</button>
          <button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Следующие материалы</button></div>}
        <div className="flex flex-wrap gap-3"><button className={secondaryButtonClass} onClick={() => setStep(0)}>Назад к пациенту</button>
          <button className={buttonClass} disabled={loading || !!error} onClick={() => setStep(2)}>Сформулировать вопрос</button></div>
      </>}
      {step === 2 && <>
        <h2 className="text-lg font-semibold">Какое мнение вам нужно?</h2>
        <p className="rounded-xl bg-gray-50 p-4 text-sm">{patient?.fio} · материалов выбрано: {selected.length}</p>
        <label className="block text-sm">Название<input className={inputClass} maxLength={255} placeholder="Например, план наблюдения перед следующим приёмом" value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label className="block text-sm">Вопрос для обсуждения<textarea className={inputClass} rows={5} maxLength={10000} placeholder="Что важно сопоставить и на какой вопрос должен ответить коллега?" value={question} onChange={event => setQuestion(event.target.value)} /></label>
        <details className="rounded-xl border border-gray-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Пригласить коллегу сейчас (необязательно)</summary>
          <label className="mt-4 block text-sm">Найти врача<input className={inputClass} value={doctorQuery} onChange={event => setDoctorQuery(event.target.value)} /></label>
          <button className={`${secondaryButtonClass} mt-3`} disabled={doctorQuery.trim().length < 2} onClick={async () => {
            try { setDoctors(await caseApi.doctors(doctorQuery)) } catch (cause) { setError(caseError(cause)) }
          }}>Найти врача</button>
          {doctors.map(doctor => <button className="mt-2 block text-sm text-primary-700" key={doctor.id} onClick={() => { setInvitee(doctor); setDoctors([]) }}>{doctor.name} · {doctor.email}</button>)}
          {invitee && <p className="mt-3 text-sm">Приглашение: {invitee.name} <button className="ml-2 underline" onClick={() => setInvitee(null)}>Убрать</button></p>}
          <p className="mt-3 text-xs text-gray-500">До принятия клинический контекст скрыт. Координатор сможет добавлять новые материалы этого пациента в разбор.</p>
        </details>
        <p className="text-xs text-gray-500">{invitee ? 'Случай станет активным после отправки приглашения.' : 'Черновик будет виден только вам. Пригласить коллег можно на экране случая.'} Незавершённая форма пока хранится только до ухода с этой страницы.</p>
        <div className="flex flex-wrap gap-3"><button className={secondaryButtonClass} disabled={busy || !!created.current} onClick={() => setStep(1)}>Назад к материалам</button>
          <button className={buttonClass} disabled={busy || !!created.current || !title.trim() || !question.trim()} onClick={() => void create()}>{invitee ? 'Создать и пригласить коллегу' : 'Создать черновик'}</button></div>
      </>}
    </section>
  </div>
}
