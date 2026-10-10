export const inputClass = 'w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-500 focus:border-primary-500 focus:ring-2 focus:ring-primary-100'
export const buttonClass = 'inline-flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50'
export const secondaryButtonClass = 'inline-flex items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40'
export const cardClass = 'rounded-2xl border border-gray-200 bg-white p-5 shadow-card space-y-4 sm:p-6'
export const stateLabel: Record<string, string> = { draft: 'Черновик', active: 'Активный', closed: 'Завершённый' }
export const stateTone: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', active: 'bg-secondary-50 text-secondary-800', closed: 'bg-primary-50 text-primary-700',
}
export const memberLabel: Record<string, string> = {
  pending: 'Приглашён', accepted: 'Участвует', declined: 'Отклонил приглашение', cancelled: 'Приглашение отозвано',
  removed: 'Исключён', left: 'Вышел из случая',
}
export const opinionLabel: Record<string, string> = { open: 'Ожидает ответа', answered: 'Ответ получен', cancelled: 'Отменён' }
export const recordTypeLabel: Record<string, string> = {
  consultation_result: 'Консультация', exam_result: 'Обследование', lab_result: 'Анализы', other: 'Другая запись',
}
export const recordStatusLabel: Record<string, string> = { confirmed: 'Подтверждена', unconfirmed: 'Не подтверждена' }
