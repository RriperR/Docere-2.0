import { useCallback, useEffect, useRef, useState } from 'react'
import type { MaterialReference } from './CaseDocumentPanel'
import api from '../../api/api'
import { caseError, type ClinicalCase, type Page } from '../../api/cases'
import { buttonClass, cardClass, inputClass } from './styles'

export interface Message {
  id: string; author_id: string; author_name: string; body: string; created_at: string; sequence: number
  parent_id: string | null; record_id: string | null; attachment_id: string | null; opinion_id: string | null
}
interface Opinion {
  id: string; requester_id: string; assignee_id: string; question: string; status: string
  record_id: string | null; reason: string | null; response_message_id: string | null
}
interface Activity { id: string; event_type: string; actor_name: string; created_at: string }
const labels: Record<string, string> = {
  case_created: 'Создан случай', draft_updated: 'Изменён черновик', invitation: 'Отправлено приглашение',
  accept: 'Принято приглашение', decline: 'Приглашение отклонено', cancel: 'Приглашение отозвано',
  leave: 'Выход из случая', remove: 'Участник исключён', message: 'Новое сообщение', message_reply: 'Ответ на сообщение',
  opinion_requested: 'Запрошено мнение', opinion_answered: 'Получен ответ', opinion_cancelled: 'Запрос отменён',
  materials_added: 'Добавлены материалы', conclusion_updated: 'Обновлён итог', closed: 'Разбор завершён', published: 'Итог опубликован',
}

export default function CaseDiscussion({ c, userId, onChange, onOpen, reference }: {
  c: ClinicalCase; userId: string; onChange: () => Promise<void>
  reference?: MaterialReference | null
  onOpen?: (recordId: string, attachmentId: string | null) => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [opinions, setOpinions] = useState<Opinion[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [opOffset, setOpOffset] = useState(0)
  const [opTotal, setOpTotal] = useState(0)
  const [actOffset, setActOffset] = useState(0)
  const [actTotal, setActTotal] = useState(0)
  const [body, setBody] = useState('')
  const [parent, setParent] = useState<Message | null>(null)
  const [replyOpinion, setReplyOpinion] = useState<Opinion | null>(null)
  const [record, setRecord] = useState('')
  const [attachment, setAttachment] = useState<string | null>(null)
  const [parentContext, setParentContext] = useState<Message | null>(null)
  useEffect(() => {
    if (reference) { setRecord(reference.recordId); setAttachment(reference.attachmentId) }
  }, [reference])
  const [question, setQuestion] = useState('')
  const [assignee, setAssignee] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const retry = useRef<{ fingerprint: string; key: string } | null>(null)
  const writable = c.status !== 'closed'
  const doctors = [{ user_id: c.coordinator_id, name: 'Координатор' }, ...c.members.filter(m => m.status === 'accepted')]
  const name = (id: string) => doctors.find(d => d.user_id === id)?.name ?? 'Врач'
  const load = useCallback(async () => {
    try {
      const [msg, op, act] = await Promise.all([
        api.get<Page<Message>>(`/cases/${c.id}/messages`, { params: { offset, limit: 20 } }),
        api.get<Page<Opinion>>(`/cases/${c.id}/opinions`, { params: { offset: opOffset, limit: 20 } }),
        api.get<Page<Activity>>(`/cases/${c.id}/activity`, { params: { offset: actOffset, limit: 20 } }),
      ])
      setMessages(msg.data.items); setTotal(msg.data.total); setOpinions(op.data.items); setOpTotal(op.data.total)
      setActivity(act.data.items); setActTotal(act.data.total)
    } catch (e) { setMessages([]); setOpinions([]); setActivity([]); setError(caseError(e)) }
  }, [c.id, offset, opOffset, actOffset])
  useEffect(() => { void load() }, [load, c.sequence])
  async function mutate(path: string, payload?: unknown) {
    setBusy(true); setError('')
    try { await api.post(`/cases/${c.id}/${path}`, payload); await onChange(); await load(); return true }
    catch (e) { setError(caseError(e)); await onChange(); return false }
    finally { setBusy(false) }
  }
  async function send() {
    const payload = { body, parent_id: parent?.id ?? null, record_id: record || null, opinion_id: replyOpinion?.id ?? null, attachment_id: attachment }
    const fingerprint = JSON.stringify(payload)
    if (retry.current?.fingerprint !== fingerprint) retry.current = { fingerprint, key: crypto.randomUUID() }
    if (await mutate('messages', { ...payload, idempotency_key: retry.current.key })) {
      setBody(''); setParent(null); setReplyOpinion(null); retry.current = null; setOffset(0)
    }
  }
  return <>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <section className={cardClass}><h2 className="text-lg font-semibold">Обсуждение</h2>
      {[...messages].reverse().map(m => <article key={m.id} className={`rounded-lg bg-gray-50 p-3 ${m.parent_id ? 'ml-6' : ''}`}>
        <p className="text-sm text-gray-500">{m.author_name} · {new Date(m.created_at).toLocaleString('ru-RU')}</p>
        {m.parent_id && <button className="text-xs text-primary-700" onClick={async () => {
          try { setParentContext((await api.get<Message>(`/cases/${c.id}/messages/${m.parent_id}`)).data) }
          catch (e) { setError(caseError(e)); await onChange() }
        }}>Показать исходное сообщение</button>}
        <p className="whitespace-pre-wrap">{m.body}</p>
        {m.record_id && <button className="text-primary-700 underline"
          onClick={() => onOpen?.(m.record_id!, m.attachment_id)}>Открыть связанный материал</button>}
        {writable && !m.parent_id && <button className="ml-4 text-primary-700" onClick={() => {
          setParent(m); setReplyOpinion(null)
        }}>Ответить</button>}
      </article>)}
      <div className="flex gap-4"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>Новые сообщения</button>
        <span>{total} сообщений</span><button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Ранее</button></div>
      {parentContext && <div className="rounded-lg border p-3"><p>{parentContext.author_name}: {parentContext.body}</p>
        <button onClick={() => setParentContext(null)}>Скрыть исходное сообщение</button></div>}
      {writable && <div className="space-y-2">
        {parent && <p>Ответ: {parent.body} <button onClick={() => setParent(null)}>Отмена</button></p>}
        {replyOpinion && <p>Ответ на запрос: {replyOpinion.question} <button onClick={() => setReplyOpinion(null)}>Отмена</button></p>}
        <label className="block">Сообщение<textarea className={inputClass} maxLength={10000} value={body} onChange={e => setBody(e.target.value)} /></label>
        <label className="block">Связанный материал<select className={inputClass} value={record} onChange={e => { setRecord(e.target.value); setAttachment(null) }}>
          <option value="">Без ссылки</option>{c.record_ids.map(id => <option key={id} value={id}>{id.slice(0, 8)}</option>)}</select></label>
        {attachment && <p>Ссылка на вложение: {reference?.label} <button onClick={() => setAttachment(null)}>Убрать вложение</button></p>}
        <p className="text-sm text-gray-500">Сообщения неизменяемы. Исправление отправьте новым ответом.</p>
        <button className={buttonClass} disabled={busy || !body.trim()} onClick={() => void send()}>Отправить сообщение</button>
      </div>}
    </section>
    <section className={cardClass}><h2 className="text-lg font-semibold">Запросы мнения</h2>
      {opinions.map(o => <article key={o.id} className="rounded-lg bg-gray-50 p-3 space-y-2">
        <p>{name(o.requester_id)} → {name(o.assignee_id)} · {o.status}</p><p>{o.question}</p>
        {o.reason && <p className="text-sm">Причина отмены: {o.reason === 'assignee_left' ? 'Адресат вышел из случая' : o.reason}</p>}
        {o.record_id && <button onClick={() => onOpen?.(o.record_id!, null)}>Открыть материал</button>}
        {writable && o.status === 'open' && o.assignee_id === userId && <button className="text-primary-700" onClick={() => {
          setReplyOpinion(o); setParent(null); setRecord(o.record_id ?? '')
        }}>Ответить на запрос</button>}
        {writable && o.status === 'open' && [o.requester_id, c.coordinator_id].includes(userId) && <button className="ml-4" disabled={busy}
          onClick={() => void mutate(`opinions/${o.id}/cancel`)}>Отменить запрос</button>}
      </article>)}
      <div className="flex gap-4"><button disabled={!opOffset} onClick={() => setOpOffset(opOffset - 20)}>Назад</button>
        <span>{opTotal} запросов</span><button disabled={opOffset + 20 >= opTotal} onClick={() => setOpOffset(opOffset + 20)}>Далее</button></div>
      {writable && <div className="space-y-2">
        <label>Адресат<select className={inputClass} value={assignee} onChange={e => setAssignee(e.target.value)}>
          <option value="">Выберите врача</option>{doctors.filter(d => d.user_id !== userId).map(d =>
            <option key={d.user_id} value={d.user_id}>{d.name}</option>)}</select></label>
        <label>Вопрос<textarea className={inputClass} maxLength={10000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        <button className={buttonClass} disabled={busy || !question.trim() || !assignee} onClick={async () => {
          if (await mutate('opinions', { assignee_id: assignee, question, record_id: record || null })) setQuestion('')
        }}>Запросить мнение</button>
      </div>}
    </section>
    <details className={cardClass}><summary className="font-semibold">Журнал действий</summary>
      {activity.map(a => <p key={a.id}>{new Date(a.created_at).toLocaleString('ru-RU')} · {a.actor_name} · {labels[a.event_type] ?? a.event_type}</p>)}
      <div className="flex gap-4"><button disabled={!actOffset} onClick={() => setActOffset(actOffset - 20)}>Назад</button>
        <span>{actTotal} событий</span><button disabled={actOffset + 20 >= actTotal} onClick={() => setActOffset(actOffset + 20)}>Далее</button></div>
    </details>
  </>
}
