import type { useCaseWorkDraft } from '../../hooks/useCaseWorkDraft'

export default function DraftStatus({ draft }: { draft: ReturnType<typeof useCaseWorkDraft> }) {
  return <div className="space-y-2 text-xs text-gray-500" aria-live="polite">
    <p>{draft.status} · хранится 7 дней</p>
    {draft.error && <p role="alert" className="text-error-700">{draft.error}</p>}
    {(draft.error || draft.conflict) && <div className="flex flex-wrap gap-3">
      {draft.ready && !draft.conflict && <button type="button" className="font-semibold underline" onClick={() => void draft.flush()}>Повторить сохранение</button>}
      <button type="button" className="font-semibold underline" onClick={() => void draft.reload()}>Перечитать сохранённый черновик</button>
    </div>}
  </div>
}
