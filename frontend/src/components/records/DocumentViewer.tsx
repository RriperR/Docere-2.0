import { ImportPatientDraft } from '../../stores/uploadStore'
import axios from 'axios'
import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../api/api'
import { caseError } from '../../api/cases'
import { inputClass, recordTypeLabel, recordStatusLabel } from '../../pages/cases/styles'
import Modal from '../common/Modal'

interface Attachment { id: string; filename: string | null; mime_type: string; size_bytes: number }
interface RecordDetail {
  patient_passport_id?: string | null;
  id: string; title: string | null; event_date: string; clinical_summary: string | null; record_type: string; status: string
  attachments: Attachment[]
  comments: { attachments: Attachment[] }[]
}
export interface MaterialReference { recordId: string; attachmentId: string | null; label: string }

export default function DocumentViewer({ caseId, patientId, importJobId, page = 1, recordId, attachmentId, onClose, onAccessLost, onReference, importFiles, onAttachmentChange }: {
  caseId?: string; patientId?: string; importJobId?: string; page?: number; recordId: string; attachmentId: string | null; onClose: () => void
  importFiles?: ImportPatientDraft['record_groups'][number]['files']; onAttachmentChange?: (id: string) => void
  onAccessLost: () => Promise<void>; onReference?: (reference: MaterialReference) => void
}) {
  const base = caseId ? `/cases/${caseId}/materials/${recordId}` : `/records/${recordId}`
  const sourceUrl = useCallback((id: string) => importJobId ? `/archives/imports/${importJobId}/files/${id}` : `${base}/attachments/${id}`, [importJobId, base])
  const [revision, setRevision] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const expandButton = useRef<HTMLButtonElement>(null)
  const wasExpanded = useRef(false)
  useEffect(() => {
    if (wasExpanded.current && !expanded) expandButton.current?.focus()
    wasExpanded.current = expanded
  }, [expanded])
  const [zoom, setZoom] = useState(1)
  useEffect(() => {
    const recheck = () => { setRecord(null); setUrl(''); setRevision(value => value + 1) }
    window.addEventListener('focus', recheck)
    return () => window.removeEventListener('focus', recheck)
  }, [])
  const fail = useCallback(async (error: unknown) => {
    setError(caseError(error))
    if (axios.isAxiosError(error) && [401, 403, 404].includes(error.response?.status ?? 0)) { setRecord(null); setUrl(''); await onAccessLost() }
  }, [onAccessLost])
  const [record, setRecord] = useState<RecordDetail | null>(null)
  const [selected, setSelected] = useState(attachmentId ?? '')
  const [url, setUrl] = useState('')
  const [mime, setMime] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setRecord(null); setError(''); setSelected(attachmentId ?? '')
    const request = importJobId
      ? importFiles
        ? Promise.resolve({ id: importJobId, title: 'Исходный документ', event_date: '', clinical_summary: null, record_type: 'other', status: 'unconfirmed',
            attachments: importFiles.filter(file => file.id).map(file => ({ ...file, id: file.id! })), comments: [] } as RecordDetail)
        : api.get<{ report_json: { patients?: ImportPatientDraft[] } }>(`/archives/imports/${importJobId}`, { signal: controller.signal }).then(result => ({
          id: importJobId, title: 'Исходный документ', event_date: '', clinical_summary: null, record_type: 'other', status: 'unconfirmed',
          attachments: (result.data.report_json.patients ?? []).flatMap(p => p.record_groups.flatMap(g => g.files)).filter(f => f.id).map(f => ({ ...f, id: f.id! })), comments: [],
        } as RecordDetail))
      : api.get<RecordDetail>(base, { signal: controller.signal }).then(result => result.data)
    void request.then(data => {
      if (controller.signal.aborted) return
      if (patientId && data.patient_passport_id !== patientId) { setError('Запись не принадлежит этому пациенту'); void onAccessLost(); return }
      setRecord({ ...data, attachments: [...data.attachments, ...data.comments.flatMap(c => c.attachments)] })
    }).catch(e => { if (!controller.signal.aborted) { void fail(e) } })
    return () => controller.abort()
  }, [base, importJobId, patientId, attachmentId, onAccessLost, revision, fail, importFiles])
  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    setUrl(''); setMime(''); if (record && selected) setError('')
    setZoom(1)
    if (selected && record && record.attachments.some(file => file.id === selected)) void api.get<Blob>(sourceUrl(selected),
      { responseType: 'blob', signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return
      const contentType = String(result.headers['content-type'] ?? '').split(';')[0]
      if (['application/pdf', 'image/png', 'image/jpeg'].includes(contentType)) {
        objectUrl = URL.createObjectURL(result.data); setUrl(objectUrl); setMime(contentType)
      } else setMime('unsupported')
    }).catch(e => { if (!controller.signal.aborted) { void fail(e) } })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [base, importJobId, sourceUrl, selected, record, revision, fail])
  async function download() {
    try {
      const file = (await api.get<Blob>(sourceUrl(selected),
        { responseType: 'blob', params: { download: true } })).data
      const objectUrl = URL.createObjectURL(file)
      const a = document.createElement('a'); a.href = objectUrl
      a.download = record?.attachments.find(f => f.id === selected)?.filename ?? 'document'
      a.click(); URL.revokeObjectURL(objectUrl)
    } catch (e) { await fail(e) }
  }
  const content = <aside aria-label="Просмотр документа" className="flex min-w-0 flex-col rounded-2xl border border-primary-200 bg-white p-5 shadow-card">
    <div className="flex flex-wrap justify-between gap-3"><h2 className="min-w-0 break-words text-xl font-semibold">{importJobId ? record?.attachments.find(file => file.id === selected)?.filename ?? 'Исходный документ' : record?.title ?? 'Материал случая'}</h2>
      <div className="flex gap-3"><button ref={expandButton} onClick={() => setExpanded(value => !value)}>{expanded ? 'Вернуть в панель' : 'На весь экран'}</button><button aria-label="Закрыть просмотр" onClick={onClose}>Закрыть</button></div></div>
    {!record && !error && <p role="status" className="py-4 text-sm text-gray-500">Загружаем материал…</p>}
    {error && <p role="alert" className="text-red-700">{error} <button className="underline" onClick={() => setRevision(value => value + 1)}>Повторить</button></p>}
    <div className="mt-4 flex-1 overflow-auto space-y-3">
      {record && <>{!importJobId && <><p className="text-xs text-gray-500">{record.event_date} · {recordTypeLabel[record.record_type] ?? 'Медицинская запись'} · {recordStatusLabel[record.status] ?? 'Статус неизвестен'}</p><p className="whitespace-pre-wrap">{record.clinical_summary}</p></>}
        {onReference && <button className="text-primary-700 underline" onClick={() => onReference({ recordId, attachmentId: null,
          label: record.title ?? 'Медицинская запись' })}>Сослаться на запись в сообщении</button>}
        <label className="block">Вложение<select aria-label="Вложение" className={inputClass} value={selected} onChange={e => { if (onAttachmentChange) onAttachmentChange(e.target.value); else setSelected(e.target.value) }}>
          <option value="">Выберите документ</option>{record.attachments.map(f => <option key={f.id} value={f.id}>{f.filename ?? 'Документ'} ({Math.ceil(f.size_bytes / 1024)} КБ)</option>)}</select></label>
        {selected && <div className="flex flex-wrap gap-3"><button onClick={() => void download()}>Скачать файл</button>
          {onReference && <button className="text-primary-700 underline" onClick={() => onReference({ recordId, attachmentId: selected,
            label: record.attachments.find(f => f.id === selected)?.filename ?? 'Документ' })}>Сослаться на вложение в сообщении</button>}</div>}
      </>}
      {url && mime === 'application/pdf' && <iframe title="Просмотр PDF" src={page > 1 ? `${url}#page=${page}` : url} referrerPolicy="no-referrer" className="h-[55vh] min-h-80 w-full rounded-lg border" />}
      {url && ['image/png', 'image/jpeg'].includes(mime) && <><div className="flex gap-3"><button aria-label="Уменьшить изображение" disabled={zoom <= 0.5} onClick={() => setZoom(value => Math.max(0.5, value - 0.25))}>−</button><span>{Math.round(zoom * 100)}%</span><button aria-label="Увеличить изображение" disabled={zoom >= 3} onClick={() => setZoom(value => Math.min(3, value + 0.25))}>+</button><button onClick={() => setZoom(1)}>По размеру панели</button></div><div className="overflow-auto"><img src={url} alt="Вложение медицинской записи" style={{ width: `${zoom * 100}%`, maxWidth: 'none' }} className="object-contain" /></div></>}
      {mime === 'unsupported' && <p>Этот формат доступен для скачивания. Полноценный DICOM-viewer здесь не используется.</p>}
    </div>
  </aside>
  return expanded ? <Modal title="Просмотр документа" onClose={() => setExpanded(false)}>{content}</Modal> : content
}
