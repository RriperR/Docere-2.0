import { Outlet } from 'react-router-dom'
import { ActivitySquare, ArrowRight, Check, Files, MessageSquare, ShieldCheck, Users } from 'lucide-react'

export const AuthLayout = () => <div className="flex min-h-screen bg-gray-50">
  <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-primary-950 p-10 text-white lg:flex xl:p-14">
    <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -right-32 h-[600px] w-[600px] rounded-full border-[80px] border-secondary-400/10" />
    <div className="relative flex items-center gap-3">
      <ActivitySquare size={32} className="text-secondary-300" aria-hidden="true" />
      <span className="text-2xl font-semibold tracking-tight">Docere</span>
      <span className="ml-auto text-xs text-primary-200">Для совместной работы врачей</span>
    </div>
    <div className="relative my-12 max-w-lg">
      <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-secondary-300">Клинический контекст объединяет</p>
      <h1 className="text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">Второе мнение.<br /><span className="text-primary-200">Общий контекст.</span></h1>
      <p className="mt-6 text-base leading-relaxed text-primary-100">Материалы пациента, обсуждение с коллегами и итог разбора — в одном рабочем пространстве.</p>
      <div className="mt-9 rounded-2xl border border-white/15 bg-white/5 p-6">
        <p className="mb-5 text-xs font-medium uppercase tracking-widest text-primary-200">От вопроса к общему результату</p>
        <ol className="space-y-5">
          {[
            { icon: Files, title: 'Выберите материалы', text: 'Только нужные записи одного пациента.' },
            { icon: MessageSquare, title: 'Обсудите с коллегами', text: 'Приглашения, вопросы и ссылки на документы.' },
            { icon: Check, title: 'Зафиксируйте итог', text: 'Сохраните выводы и дальнейшие действия.' },
          ].map(({ icon: Icon, title, text }) => <li key={title} className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-secondary-200"><Icon size={20} aria-hidden="true" /></div>
            <div><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-sm text-primary-200">{text}</p></div>
          </li>)}
        </ol>
      </div>
    </div>
    <div className="relative flex items-center gap-2 text-xs text-primary-200"><ShieldCheck size={16} aria-hidden="true" />Доступ к материалам — по приглашению и с возможностью отзыва.</div>
  </aside>
  <main className="flex min-w-0 flex-1 flex-col items-center justify-center px-5 py-10 sm:px-10">
    <div className="mb-8 flex items-center gap-2 lg:hidden"><ActivitySquare size={28} className="text-primary-600" aria-hidden="true" /><span className="text-2xl font-semibold text-gray-900">Docere</span></div>
    <div className="mb-6 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-gray-500"><Users size={16} aria-hidden="true" />Рабочее пространство врача</div>
    <div className="w-full max-w-md rounded-3xl border border-gray-200 bg-white p-6 shadow-card sm:p-8"><Outlet /></div>
    <p className="mt-6 flex max-w-sm items-center gap-2 text-center text-xs leading-relaxed text-gray-500"><ArrowRight size={14} className="shrink-0" aria-hidden="true" />История пациента и совместные разборы в одном месте.</p>
  </main>
</div>
