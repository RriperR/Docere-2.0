import { Link } from 'react-router-dom'
import InboxTasks from './InboxTasks'
import { cardClass } from './styles'
export default function Attention() {
  return <section className={cardClass}><div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Требует внимания</h2><Link className="text-sm font-semibold text-primary-700" to="/notifications">Все входящие →</Link></div><InboxTasks limit={5} /></section>
}
