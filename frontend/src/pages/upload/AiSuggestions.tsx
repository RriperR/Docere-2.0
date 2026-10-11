import { AiDocument, aiErrorLabels, AiFieldName, aiFieldLabels, aiIssueLabel, AppliedAi } from '../../api/importAi'
import { Button } from '../../components/common/Button'

export default function AiSuggestions({ document, runId, onApply, onSource, canApplyIdentity }: {
  document: AiDocument; runId: string; canApplyIdentity: boolean
  onApply: (name: AiFieldName, value: string, reference: AppliedAi, emptyOnly?: boolean) => void
  onSource: (fileId: string, page: number) => void
}) {
  const fields = Object.entries(document.result.fields ?? {}) as [AiFieldName, NonNullable<AiDocument['result']['fields']>[AiFieldName]][]
  return <section aria-label="AI-предложения" className="mt-4 space-y-3 rounded-xl border border-primary-200 bg-primary-50/40 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold text-primary-900">Предложения AI</h4>
      {document.status === 'completed' && <Button size="sm" variant="outline" onClick={() => fields.forEach(([name, field]) => { if (field && (!['fio', 'date_of_birth'].includes(name) || canApplyIdentity)) onApply(name, field.value, { run_id: runId, file_id: document.file_id, fields: [name] }, true) })}>Заполнить пустые поля</Button>}
    </div>
    {document.status === 'queued' && <p role="status" className="text-sm">Документ ожидает анализа…</p>}
    {document.error_code && <p role="alert" className="text-sm text-red-700">{aiErrorLabels[document.error_code] ?? 'Не удалось обработать документ.'}</p>}
    {document.result.multiple_patients && <p className="text-sm text-red-700">В документе разные пациенты. Пропустите его и загрузите раздельные файлы.</p>}
    {fields.map(([name, field]) => field && <div key={name} className="rounded-lg bg-white p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{aiFieldLabels[name]}</span>
        <button disabled={['fio', 'date_of_birth'].includes(name) && !canApplyIdentity} className="text-primary-700 underline disabled:text-gray-400" onClick={() => onApply(name, field.value, { run_id: runId, file_id: document.file_id, fields: [name] })}>Применить поле</button></div>
      <p className="mt-1 whitespace-pre-wrap break-words">{name === 'record_type' ? ({ consultation_result: 'Консультация', exam_result: 'Обследование', lab_result: 'Анализ', other: 'Другое' }[field.value] ?? field.value) : field.value}</p>
      {field.sources.map((source, index) => <button key={`${source.page}-${index}`} className="mt-2 block max-w-full text-left text-xs text-primary-700 underline break-words" onClick={() => onSource(document.file_id, source.page)}>Стр. {source.page}: «{source.excerpt}»</button>)}
    </div>)}
    {!!document.result.issues?.length && <details><summary className="cursor-pointer text-sm">Что требует проверки ({document.result.issues.length})</summary><ul className="mt-2 space-y-1 text-xs text-gray-600">{document.result.issues.map((issue, i) => <li key={i}>{aiIssueLabel(issue)}</li>)}</ul></details>}
    <p className="text-xs text-gray-500">Проверьте предложения по оригиналу. Ссылка на страницу не гарантирует правильность распознавания.</p>
  </section>
}
