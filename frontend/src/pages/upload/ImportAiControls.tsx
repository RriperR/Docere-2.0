import type { ImportPatientDraft } from '../../stores/uploadStore'
import { aiErrorLabels, aiStatusLabels } from '../../api/importAi'
import { Button } from '../../components/common/Button'
import type { useImportAi } from './useImportAi'

type AiControlsProps = {
  ai: ReturnType<typeof useImportAi>
  patientCandidates: ImportPatientDraft[]
  selection: string[]
  onSelectionChange: (update: (current: string[]) => string[]) => void
  saving: boolean
  errorCode?: string | null
}

/** Управление внешним анализом с видимым прогрессом даже при свёрнутых настройках. */
export default function ImportAiControls({ ai, patientCandidates, selection: aiSelection, onSelectionChange: setAiSelection, saving: isSavingReviewDraft, errorCode }: AiControlsProps) {
  const documents = ai.run?.documents ?? []
  const completed = documents.filter(document => document.status === 'completed').length
  const failed = documents.filter(document => document.status === 'failed').length
  const cancelled = documents.filter(document => document.status === 'cancelled').length
  const running = documents.filter(document => ['queued', 'running'].includes(document.status)).length
  const error = ai.error || (errorCode ? aiErrorLabels[errorCode] || 'Автоматический анализ недоступен.' : '')
  return <div className="space-y-3">
    {ai.active && <div className="flex flex-wrap items-center gap-3 rounded-lg border border-primary-200 bg-primary-50 p-3">
      <p role="status" className="text-sm">Анализ выполняется…</p>
      <Button variant="outline" disabled={!ai.run || ai.busy} onClick={() => void ai.cancel()}>Отменить анализ</Button>
    </div>}
    {ai.run && <p role="status" className="text-sm text-gray-600">
      {ai.run.status === 'completed' && 'Предложения готовы — проверьте по документу. '}
      Завершено документов: {completed} из {documents.length}. В очереди и выполняются: {running}. Ошибки: {failed}. Отменено: {cancelled}.
    </p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <details className="rounded-xl border border-gray-200 bg-white p-4">
        <summary className="cursor-pointer font-medium">Заполнить поля по документам с AI</summary>
        <div className="mt-4">
        <p className="mb-3 text-sm text-gray-600">Выберите документы для передачи внешнему сервису. AI предлагает факты; вы проверяете оригиналы и решаете, какие поля применить.</p>
        {ai.capabilities?.enabled && <p className="text-xs text-gray-500">До {ai.capabilities.max_documents} документов и {ai.capabilities.max_pages} страниц за запуск; до {ai.capabilities.max_pages_per_document} страниц в одном документе.</p>}
        {!ai.capabilities?.enabled && <p className="text-sm text-gray-500">AI-сервис пока не настроен. Обычный импорт доступен.</p>}
        <div className="my-3 grid gap-2 md:grid-cols-2">{patientCandidates.flatMap(p => p.record_groups.flatMap(g => g.files)).filter(f => f.id && !f.is_dicom && ['application/pdf', 'image/png', 'image/jpeg'].includes(f.mime_type)).map(file => <label key={file.id} className="flex min-w-0 items-center gap-2 text-sm"><input type="checkbox" disabled={ai.active} checked={aiSelection.includes(file.id!)} onChange={e => setAiSelection(current => e.target.checked ? [...current, file.id!] : current.filter(id => id !== file.id))} /><span className="break-all">{file.filename}</span></label>)}</div>
        <div className="flex flex-wrap items-center gap-3"><Button disabled={!ai.capabilities?.enabled || !aiSelection.length || ai.active || isSavingReviewDraft} isLoading={ai.busy} onClick={() => void ai.start(aiSelection)}>Проанализировать выбранные</Button>
        </div>
        {ai.run && <p className="mt-3 text-xs text-gray-500">{ai.run.provider} · {ai.run.model}</p>}
        {!!ai.history.length && <div className="mt-3 flex flex-wrap items-center gap-3"><label className="text-sm">Версия предложений<select className="ml-2 rounded-md border p-2" value={ai.run?.id ?? ''} onChange={e => { const run = ai.history.find(r => r.id === e.target.value); if (run) ai.selectRun(run) }}><option value="">Последний запуск</option>{ai.history.map(run => <option key={run.id} value={run.id}>{new Date(run.created_at).toLocaleString('ru-RU')} · {aiStatusLabels[run.status] ?? run.status}</option>)}</select></label>{ai.hasOlder && <Button size="sm" variant="outline" onClick={() => void ai.loadOlder()}>Предыдущие запуски</Button>}</div>}
        </div>
      </details>
  </div>
}
