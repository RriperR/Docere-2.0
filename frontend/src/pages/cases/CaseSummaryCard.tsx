import { ArrowUpRight, FileText, LockKeyhole, MessageSquare, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CaseView } from '../../api/cases'
import { stateLabel, stateTone } from './styles'

/** Карточка использует только разрешённое сервером представление случая. */
export default function CaseSummaryCard({ item }: { item: CaseView }) {
  const clinical = item.accessible ? item.case : null
  const pending = item.membership_status === 'pending'
  return <Link to={`/cases/${item.id}`}
    className="group flex h-full min-w-0 flex-col rounded-2xl border border-gray-200 bg-white p-5 shadow-card transition-colors hover:border-primary-300 hover:bg-primary-50/30 sm:p-6">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${stateTone[item.status] ?? stateTone.draft}`}>
        {stateLabel[item.status] ?? 'Клинический случай'}
      </span>
      {pending ? <span className="text-xs font-medium text-warning-700">Ожидает вашего ответа</span> :
        item.unread_messages > 0 && clinical && <span className="flex items-center gap-1.5 text-xs font-semibold text-primary-700">
          <MessageSquare size={14} aria-hidden="true" />Новых сообщений: {item.unread_messages}
        </span>}
    </div>
    <div className="flex items-start justify-between gap-3">
      <h2 className="text-lg font-semibold leading-snug text-gray-900 group-hover:text-primary-700">
        {clinical?.title ?? (pending ? 'Приглашение в разбор' : 'Случай недоступен')}
      </h2>
      <ArrowUpRight size={19} className="shrink-0 text-gray-400 group-hover:text-primary-600" aria-hidden="true" />
    </div>
    {clinical ? <>
      <p className="mt-2 flex items-center gap-2 text-sm text-gray-600"><UserRound size={15} aria-hidden="true" />{item.patient_name}</p>
      <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-gray-600">{clinical.question}</p>
    </> : <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-gray-500">
      <LockKeyhole size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      {pending ? 'Материалы и обсуждение откроются после принятия приглашения.' : 'Клинические сведения скрыты. Откройте карточку, чтобы проверить участие.'}
    </p>}
    <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-4 text-xs text-gray-500">
      <span className="mt-2">Координатор: {item.coordinator_name}</span>
      <span className="mt-2 flex items-center gap-1.5"><FileText size={14} aria-hidden="true" />Материалов: {item.material_count}</span>
    </div>
  </Link>
}
