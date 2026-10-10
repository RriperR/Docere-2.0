import { useEffect, useState } from 'react'
import api from '../../api/api'
import { caseError } from '../../api/cases'
import { inputClass, recordTypeLabel, recordStatusLabel } from './styles'

interface Attachment { id: string; filename: string | null; mime_type: string; size_bytes: number }
interface RecordDetail {
  id: string; title: string | null; event_date: string; clinical_summary: string | null; record_type: string; status: string
  attachments: Attachment[]
  comments: { attachments: Attachment[] }[]
}
export interface MaterialReference { recordId: string; attachmentId: string | null; label: string }

export default function CaseDocumentPanel({ caseId, recordId, attachmentId, onClose, onAccessLost, onReference }: {
  caseId: string; recordId: string; attachmentId: string | null; onClose: () => void
  onAccessLost: () => Promise<void>; onReference: (reference: MaterialReference) => void
}) {
  const [record, setRecord] = useState<RecordDetail | null>(null)
  const [selected, setSelected] = useState(attachmentId ?? '')
  const [url, setUrl] = useState('')
  const [mime, setMime] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setRecord(null); setError(''); setSelected(attachmentId ?? '')
    void api.get<RecordDetail>(`/cases/${caseId}/materials/${recordId}`, { signal: controller.signal }).then(result => {
      setRecord({ ...result.data, attachments: [...result.data.attachments, ...result.data.comments.flatMap(c => c.attachments)] })
    }).catch(e => { if (!controller.signal.aborted) { setError(caseError(e)); void onAccessLost() } })
    return () => controller.abort()
  }, [caseId, recordId, attachmentId, onAccessLost])
  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    setUrl(''); setMime(''); setError('')
    if (selected) void api.get<Blob>(`/cases/${caseId}/materials/${recordId}/attachments/${selected}`,
      { responseType: 'blob', signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return
      const contentType = String(result.headers['content-type'] ?? '').split(';')[0]
      if (['application/pdf', 'image/png', 'image/jpeg'].includes(contentType)) {
        objectUrl = URL.createObjectURL(result.data); setUrl(objectUrl); setMime(contentType)
      } else setMime('unsupported')
    }).catch(e => { if (!controller.signal.aborted) { setError(caseError(e)); void onAccessLost() } })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [caseId, recordId, selected, onAccessLost])
  async function download() {
    try {
      const file = (await api.get<Blob>(`/cases/${caseId}/materials/${recordId}/attachments/${selected}`,
        { responseType: 'blob', params: { download: true } })).data
      const objectUrl = URL.createObjectURL(file)
      const a = document.createElement('a'); a.href = objectUrl
      a.download = record?.attachments.find(f => f.id === selected)?.filename ?? 'document'
      a.click(); URL.revokeObjectURL(objectUrl)
    } catch (e) { setError(caseError(e)); await onAccessLost() }
  }
  return <aside role="dialog" aria-label="Материал случая" className="flex min-w-0 flex-col rounded-2xl border border-primary-200 bg-white p-5 shadow-card">
    <div className="flex justify-between"><h2 className="text-xl font-semibold">{record?.title ?? 'Материал случая'}</h2>
      <button aria-label="Закрыть просмотр" onClick={onClose}>✕</button></div>
    {!record && !error && <p role="status" className="py-4 text-sm text-gray-500">Загружаем материал…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="mt-4 flex-1 overflow-auto space-y-3">
      {record && <><p className="text-xs text-gray-500">{record.event_date} · {recordTypeLabel[record.record_type] ?? 'Медицинская запись'} · {recordStatusLabel[record.status] ?? 'Статус неизвестен'}</p><p className="whitespace-pre-wrap">{record.clinical_summary}</p>
        <button className="text-primary-700 underline" onClick={() => onReference({ recordId, attachmentId: null,
          label: record.title ?? 'Медицинская запись' })}>Сослаться на запись в сообщении</button>
        <label className="block">Вложение<select aria-label="Вложение" className={inputClass} value={selected} onChange={e => setSelected(e.target.value)}>
          <option value="">Выберите документ</option>{record.attachments.map(f => <option key={f.id} value={f.id}>{f.filename ?? 'Документ'} ({f.size_bytes} байт)</option>)}</select></label>
        {selected && <div className="flex flex-wrap gap-3"><button onClick={() => void download()}>Скачать файл</button>
          <button className="text-primary-700 underline" onClick={() => onReference({ recordId, attachmentId: selected,
            label: record.attachments.find(f => f.id === selected)?.filename ?? 'Документ' })}>Сослаться на вложение в сообщении</button></div>}
      </>}
      {url && mime === 'application/pdf' && <iframe title="Просмотр PDF" src={url} referrerPolicy="no-referrer" className="h-[55vh] min-h-80 w-full rounded-lg border" />}
      {url && ['image/png', 'image/jpeg'].includes(mime) && <img src={url} alt="Вложение медицинской записи" className="max-h-[60vh] max-w-full object-contain" />}
      {mime === 'unsupported' && <p>Этот формат доступен для скачивания. Полноценный DICOM-viewer здесь не используется.</p>}
    </div>
  </aside>
}
