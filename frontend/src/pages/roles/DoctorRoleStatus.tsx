import { Link } from 'react-router-dom'
import type { DoctorRoleApplication } from '../../stores/doctorRoleApplicationsStore'
import { buttonClass, secondaryButtonClass } from '../cases/styles'
import { useMyDoctorApplications } from './useMyDoctorApplications'

export function RejectedApplication({ application }: { application: DoctorRoleApplication }) {
  const notes = application.reviews.filter(review => review.status === 'rejected' && review.note)
  return <div className="space-y-2">
    <h2 className="font-semibold text-gray-900">Заявка на роль врача отклонена</h2>
    {notes.length ? notes.map(review => <p key={review.id} className="break-words text-sm text-gray-700">{review.reviewer_fio}: {review.note}</p>)
      : <p className="text-sm text-gray-600">Проверяющий не указал причину отказа.</p>}
    <p className="text-sm text-gray-600">Вы можете уточнить данные и отправить новую заявку. До подтверждения вам доступен кабинет пациента.</p>
  </div>
}

export default function DoctorRoleStatus() {
  const { current, loading, error, retry } = useMyDoctorApplications()
  return <section aria-label="Роль врача" className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 sm:p-6">
    {loading ? <p role="status" className="text-sm text-gray-500">Проверяем статус заявки врача…</p>
      : error ? <div role="alert" className="space-y-3"><p>Не удалось загрузить статус заявки врача.</p><button className={secondaryButtonClass} onClick={retry}>Повторить проверку заявки</button></div>
      : current?.status === 'pending' ? <>
        <h2 className="font-semibold text-gray-900">Заявка на роль врача на проверке</h2>
        <p className="text-sm text-gray-600">Дождитесь решения выбранного администратора или двух врачей вашей специализации. Пока можно просматривать свою историю. Повторная заявка не требуется.</p>
        <Link to="/doctor-role-request" className={secondaryButtonClass}>Посмотреть заявку</Link>
      </> : current?.status === 'approved' ? <>
        <h2 className="font-semibold text-gray-900">Заявка на роль врача одобрена</h2>
        <p className="text-sm text-gray-600">Откройте заявку, чтобы обновить роль и перейти к работе врача.</p>
        <Link to="/doctor-role-request" className={buttonClass}>Перейти к работе врача</Link>
      </> : current?.status === 'rejected' ? <>
        <RejectedApplication application={current} />
        <Link to="/doctor-role-request" className={secondaryButtonClass}>Уточнить данные заявки</Link>
      </> : <>
        <h2 className="font-semibold text-gray-900">Вы врач?</h2>
        <p className="text-sm text-gray-600">Подайте заявку на подтверждение квалификации, чтобы добавлять пациентов и работать с коллегами.</p>
        <Link to="/doctor-role-request" className={secondaryButtonClass}>Я врач</Link>
      </>}
  </section>
}
