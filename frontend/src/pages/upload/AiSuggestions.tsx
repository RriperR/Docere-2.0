import { AiDocument, aiErrorLabels, AiFieldName, aiFieldLabels, aiIssueLabel, AppliedAi } from '../../api/importAi'
import { Button } from '../../components/common/Button'

interface AiSuggestionsProps {
  document: AiDocument
  runId: string
  canApplyIdentity: boolean
  currentValues?: Partial<Record<AiFieldName, string | null>>
  onApply: (name: AiFieldName, value: string, reference: AppliedAi, emptyOnly?: boolean) => void
  onSource: (fileId: string, page: number) => void
}

function displayValue(name: AiFieldName, value: string): string {
  if (name !== 'record_type') return value
  const labels: Record<string, string> = {
    consultation_result: 'Консультация', exam_result: 'Обследование', lab_result: 'Анализ', other: 'Другое',
  }
  return labels[value] ?? value
}

/** Сравнивает предложения с формой; применение и подтверждение замены остаются у review workflow. */
export default function AiSuggestions({ document, runId, onApply, onSource, canApplyIdentity, currentValues }: AiSuggestionsProps) {
  const fields = Object.entries(document.result.fields ?? {}) as [AiFieldName, NonNullable<AiDocument['result']['fields']>[AiFieldName]][]
  const canApply = document.status === 'completed' && !document.result.multiple_patients
  const identityAllowed = (name: AiFieldName) => !['fio', 'date_of_birth'].includes(name) || canApplyIdentity
  const emptyFields = fields.filter(([name, field]) => field && identityAllowed(name) && !currentValues?.[name])
  const reference = (name: AiFieldName): AppliedAi => ({ run_id: runId, file_id: document.file_id, fields: [name] })

  return <section aria-label="AI-предложения" className="mt-4 space-y-3 rounded-xl border border-primary-200 bg-primary-50/40 p-3">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><h4 className="font-semibold text-primary-900">Предложения по документу · AI</h4>
        {document.status === 'completed' && <p className="mt-1 text-xs text-gray-600">Предложения готовы — проверьте по документу. Поля формы изменятся только после применения.</p>}
      </div>
      {canApply && <Button type="button" size="sm" variant="outline" disabled={!emptyFields.length}
        onClick={() => emptyFields.forEach(([name, field]) => { if (field) onApply(name, field.value, reference(name), true) })}>
        Заполнить пустые поля
      </Button>}
    </div>
    {document.status === 'queued' && <p role="status" className="text-sm text-gray-700">Документ ожидает анализа…</p>}
    {document.status === 'running' && <p role="status" className="text-sm text-gray-700">Анализируем документ. Ваши правки сохраняются.</p>}
    {document.status === 'cancelled' && <p role="status" className="text-sm text-gray-700">Анализ документа отменён. Продолжите проверку вручную.</p>}
    {document.error_code && <p role="alert" className="text-sm text-red-700">{aiErrorLabels[document.error_code] ?? 'Не удалось обработать документ.'}</p>}
    {document.status === 'failed' && !document.error_code && <p role="alert" className="text-sm text-red-700">Не удалось обработать документ. Продолжите проверку вручную или повторите анализ.</p>}
    {document.result.multiple_patients && <p role="alert" className="text-sm text-red-700">В документе разные пациенты. Пропустите его и загрузите раздельные файлы.</p>}
    {document.result.patient_conflict && <p role="alert" className="text-sm text-red-700">Сведения о пациенте противоречат другим материалам. Проверьте принадлежность документа перед сохранением.</p>}
    {!!document.result.issues?.length && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <p className="font-medium">Требует проверки</p>
      <ul className="mt-1 list-inside list-disc space-y-1">{document.result.issues.map((issue, index) => <li key={index}>{aiIssueLabel(issue)}</li>)}</ul>
    </div>}
    <div className="space-y-2">{fields.map(([name, field]) => {
      if (!field) return null
      const current = currentValues?.[name]
      const same = current === field.value
      const replace = Boolean(current) && !same
      return <article key={name} aria-label={`Предложение: ${aiFieldLabels[name]}`} className="rounded-lg border border-gray-200 bg-white p-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h5 className="font-medium text-gray-900">{aiFieldLabels[name]}</h5>
          {same ? <span className="text-xs text-gray-600">Совпадает с формой</span> : <Button type="button" size="sm" variant="outline"
            disabled={!canApply || !identityAllowed(name)}
            aria-label={`${replace ? 'Заменить' : 'Применить'}: ${aiFieldLabels[name]}`}
            onClick={() => onApply(name, field.value, reference(name))}>
            {replace ? 'Заменить значение' : 'Применить поле'}
          </Button>}
        </div>
        <dl className="mt-2 grid min-w-0 gap-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 14rem), 1fr))' }}>
          {currentValues && <div className="min-w-0 rounded-md bg-gray-50 p-2">
            <dt className="text-xs text-gray-500">В форме сейчас</dt>
            <dd className="mt-1 whitespace-pre-wrap break-words text-gray-700">{current ? displayValue(name, current) : 'Не заполнено'}</dd>
          </div>}
          <div className="min-w-0 rounded-md bg-primary-50/60 p-2">
            <dt className="text-xs text-primary-700">Предложение AI</dt>
            <dd className="mt-1 whitespace-pre-wrap break-words text-gray-900">{displayValue(name, field.value)}</dd>
          </div>
        </dl>
        {!identityAllowed(name) && <p className="mt-2 text-xs text-gray-600">Для существующей карты данные пациента здесь не изменяются.</p>}
        {!!field.sources.length && <details className="mt-2">
          <summary className="cursor-pointer rounded-sm text-xs text-primary-700 focus-visible:outline-2 focus-visible:outline-primary-600">Источники предложения ({field.sources.length})</summary>
          <div className="mt-2 space-y-2">{field.sources.map((source, index) => <button type="button" key={`${source.page}-${index}`}
            className="block max-w-full rounded-sm text-left text-xs text-primary-700 underline break-words focus-visible:outline-2 focus-visible:outline-primary-600"
            onClick={() => onSource(document.file_id, source.page)}>Стр. {source.page}: «{source.excerpt}»</button>)}</div>
        </details>}
      </article>
    })}</div>
    <p className="text-xs text-gray-500">Ссылка на страницу показывает источник, но не гарантирует правильность распознавания.</p>
  </section>
}
