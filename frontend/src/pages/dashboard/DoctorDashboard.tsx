import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, ChevronRight, FileText, Plus, UploadCloud, Users } from 'lucide-react'
import RecentCases from './RecentCases'
import DashboardInbox from './DashboardInbox'
import { secondaryButtonClass } from '../cases/styles'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import { useUploadStore } from '../../stores/uploadStore'
import { importTitle } from '../../utils/importDisplay'

function getInitials(fio: string): string {
  return fio.trim().split(/\s+/).slice(0, 2).map(part => part[0] ?? '').join('').toUpperCase() || '?'
}

export default function DoctorDashboard() {
  const { user } = useAuthStore()
  const { patients, fetchPatients, error: patientsError } = usePatientsStore()
  const { jobs, listJobs, error: importsError } = useUploadStore()
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void Promise.all([fetchPatients(), listJobs()]).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [fetchPatients, listJobs, revision])

  const startingWork = !loading && !patientsError && !patients.some(patient => patient.accessContext !== 'own_confirmed')
  const totalRecords = useMemo(() => patients.reduce((acc, patient) => acc + patient.recordCount, 0), [patients])
  const recentPatients = useMemo(() => [...patients].sort((a, b) =>
    (b.lastVisit ? new Date(b.lastVisit).getTime() : 0) - (a.lastVisit ? new Date(a.lastVisit).getTime() : 0),
  ).slice(0, 4), [patients])
  const importIssues = jobs.filter(job => ['failed', 'completed_with_warnings'].includes(job.status)).slice(0, 3)
  const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })

  return <div className="space-y-6 sm:space-y-8">
    <section aria-labelledby="dashboard-title" className="relative overflow-hidden rounded-2xl bg-primary-950 p-5 text-white sm:p-7">
      <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-32 h-80 w-80 rounded-full border-[45px] border-secondary-400/10" />
      <div className="relative flex flex-wrap items-center justify-between gap-2 text-xs text-primary-200">
        <span>Здравствуйте, {user?.first_name || 'доктор'}</span><span>{today}</span>
      </div>
      <div className="relative mt-4 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-xl"><h1 id="dashboard-title" className="text-2xl font-semibold tracking-tight sm:text-3xl">Рабочий стол</h1>
          <p className="mt-2 text-sm leading-relaxed text-primary-100">{startingWork ? 'Добавьте пациента, чтобы собрать его историю и начать разбор с коллегами.' : 'Материалы пациента, мнение коллег и итог разбора — в одном пространстве.'}</p></div>
        <div className="flex flex-col gap-2 sm:flex-row xl:shrink-0">
          <Link to={startingWork ? '/patients?create=1' : '/cases/new'} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-primary-950 hover:bg-primary-50">
            <Plus size={17} aria-hidden="true" />{startingWork ? 'Добавить пациента' : 'Новый клинический случай'}</Link>
          <Link to="/upload" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/25 px-4 py-3 text-sm font-medium text-white hover:bg-white/10">
            <UploadCloud size={17} aria-hidden="true" />{startingWork ? 'Импорт документов' : 'Импортировать материалы'}</Link>
        </div>
      </div>
    </section>

    {startingWork && <section aria-labelledby="start-work-title" className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6">
      <h2 id="start-work-title" className="font-semibold text-gray-900">Первый разбор за три шага</h2>
      <ol className="mt-4 grid gap-4 sm:grid-cols-3">{[
        ['Добавьте пациента', 'Создайте карточку для его медицинской истории.'],
        ['Соберите материалы', 'Загрузите документы и проверьте записи перед импортом.'],
        ['Обсудите с коллегой', 'Сформулируйте вопрос, получите мнение и сохраните итог.'],
      ].map(([title, text], index) => <li key={title} className="flex gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-50 text-xs font-semibold text-primary-700" aria-hidden="true">{index + 1}</span>
        <div><h3 className="text-sm font-semibold text-gray-900">{title}</h3><p className="mt-1 text-xs leading-relaxed text-gray-500">{text}</p></div>
      </li>)}</ol>
      {patients.some(patient => patient.accessContext === 'own_confirmed') && <p className="mt-4 border-t border-gray-100 pt-4 text-xs text-gray-500">Ваша собственная карточка доступна ниже. Для работы с пациентом добавьте отдельную карточку.</p>}
    </section>}

    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <div className="min-w-0 xl:order-2"><DashboardInbox /></div>
      <div className="min-w-0 xl:order-1"><RecentCases needsPatient={startingWork} /></div>
    </div>

    <section aria-labelledby="recent-patients-title" className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 p-5 sm:px-6">
        <div><h2 id="recent-patients-title" className="text-lg font-semibold text-gray-900">Карточки пациентов</h2>
          <p className="mt-1 text-sm text-gray-500">{loading || patientsError ? 'История и материалы доступных вам пациентов' : `Карточек: ${patients.length} · Записей: ${totalRecords}`}</p></div>
        <Link to="/patients" className="flex min-h-10 items-center gap-1 text-sm font-semibold text-primary-700">Все пациенты <ArrowUpRight size={16} aria-hidden="true" /></Link>
      </div>
      {loading ? <p role="status" className="p-6 text-sm text-gray-500">Загружаем пациентов…</p> : patientsError ?
        <p role="alert" className="p-6 text-sm text-error-700">{patientsError} <button className="ml-2 font-semibold underline" onClick={() => setRevision(value => value + 1)}>Повторить</button></p> : !recentPatients.length ?
          <div className="flex flex-col items-start gap-3 p-5 sm:p-6"><Users size={24} className="text-primary-600" aria-hidden="true" />
            <div><h3 className="font-semibold text-gray-900">Пациентов пока нет</h3><p className="mt-1 text-sm text-gray-500">Начните с карточки пациента — здесь будет его история и материалы для разбора.</p></div>
            <Link className={secondaryButtonClass} to="/patients?create=1">Добавить пациента <ArrowRight size={16} aria-hidden="true" /></Link></div> :
          <div className="grid divide-y divide-gray-100 sm:grid-cols-2 sm:divide-y-0">{recentPatients.map(patient => <Link key={patient.id} to={`/patients/${patient.id}`} className="group flex min-w-0 items-center gap-3 p-5 transition-colors hover:bg-primary-50/40 sm:px-6">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50 text-xs font-semibold text-primary-700" aria-hidden="true">{getInitials(patient.fio)}</span>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-gray-900 group-hover:text-primary-700">{patient.fio}</p>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500"><span className="inline-flex items-center gap-1"><FileText size={13} aria-hidden="true" />Записей: {patient.recordCount}</span>
                {patient.accessContext === 'own_confirmed' ? <span>Ваша карточка</span> : patient.lastVisit && <span>Последняя запись: {new Date(patient.lastVisit).toLocaleDateString('ru-RU')}</span>}</p></div>
            <ChevronRight size={16} className="shrink-0 text-gray-400" aria-hidden="true" />
          </Link>)}</div>}
    </section>

    {!loading && (importsError || importIssues.length > 0) && <section aria-labelledby="import-issues-title" className="rounded-2xl border border-warning-200 bg-warning-50/50 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="import-issues-title" className="font-semibold text-gray-900">Проверьте результат импорта</h2><Link to="/upload" className="text-sm font-semibold text-primary-700">Все импорты →</Link></div>
      {importsError ? <p role="alert" className="mt-3 text-sm text-error-700">Не удалось загрузить импорты. <button className="font-semibold underline" onClick={() => setRevision(value => value + 1)}>Повторить загрузку импортов</button></p> :
        <div className="mt-3 space-y-2">{importIssues.map(job => <Link key={job.id} to={`/upload/status/${job.id}`} className="flex items-center justify-between gap-3 rounded-xl bg-white p-3 text-sm hover:bg-warning-50">
          <div className="min-w-0"><p className="font-semibold text-gray-900">{job.status === 'failed' ? 'Разобрать ошибку импорта' : 'Импорт с предупреждениями'}</p><p className="mt-1 break-words text-gray-500">{importTitle(job)}</p></div><ChevronRight size={16} className="shrink-0 text-gray-400" aria-hidden="true" /></Link>)}</div>}
    </section>}
  </div>
}
