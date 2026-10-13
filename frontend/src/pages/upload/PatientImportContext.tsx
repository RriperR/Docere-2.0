import { formatDateForDisplay } from '../../utils/dates'
import { type usePatientImportContext } from './usePatientImportContext'

export function PatientImportContext({ context }: { context: ReturnType<typeof usePatientImportContext> }) {
  if (!context.patientId) return null
  return <div className={`rounded-xl border p-4 text-sm ${context.error ? 'border-error-200 bg-error-50' : 'border-primary-100 bg-primary-50'}`}>
    {context.error ? <><p role="alert">Карточка из ссылки недоступна. Проверьте права доступа или продолжите без неё.</p>
      <button type="button" className="mt-2 mr-4 underline" onClick={context.retry}>Повторить проверку карточки</button></>
      : context.patient ? <><p className="font-semibold">Импорт для пациента: {context.patient.fio}</p>
        <p className="mt-1 text-gray-600">{context.patient.date_of_birth ? `Дата рождения: ${formatDateForDisplay(context.patient.date_of_birth)}` : 'Дата рождения не указана'}</p>
        <p className="mt-1 text-gray-600">Карточка — это человек. При проверке явно выберите, какие документы относятся к нему. Запись — событие или документ; загрузка ещё не добавляет записи в историю.</p></>
        : <p role="status">Проверяем доступ к карточке…</p>}
    <button type="button" className="mt-2 underline" onClick={context.clear}>Продолжить без карточки</button>
  </div>
}
