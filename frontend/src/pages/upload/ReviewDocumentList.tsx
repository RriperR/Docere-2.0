import type { ReviewDocument } from './reviewState'

const labels = { ready: 'Можно сохранить', needs_data: 'Нужны данные', skipped: 'Пропущен' }

export default function ReviewDocumentList({ documents, selectedId, onSelect, disabled = false }: {
  documents: ReviewDocument[]
  selectedId: string | null
  onSelect: (groupId: string) => void
  disabled?: boolean
}) {
  return <nav aria-label="Документы импорта" className="min-w-0 rounded-xl border border-gray-200 bg-white p-3 xl:sticky xl:top-20 xl:self-start">
    <h2 className="mb-2 text-sm font-semibold text-gray-900">Документы ({documents.length})</h2>
    <div className="flex max-h-60 flex-col gap-2 overflow-y-auto xl:max-h-[70vh]">
      {documents.map((document, index) => <button key={document.groupId} type="button" disabled={disabled}
        aria-current={selectedId === document.groupId ? 'true' : undefined}
        onClick={() => onSelect(document.groupId)}
        className={`min-w-0 rounded-lg border p-3 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary-500 ${selectedId === document.groupId ? 'border-primary-400 bg-primary-50' : 'border-gray-100 hover:border-primary-300'}`}>
        <span className="block break-words font-medium text-gray-900">{index + 1}. {document.filename}</span>
        <span className="mt-1 block break-words text-xs text-gray-500">{document.patientName}</span>
        <span className={`mt-2 block text-xs font-medium ${document.status === 'needs_data' ? 'text-warning-700' : document.status === 'ready' ? 'text-success-700' : 'text-gray-500'}`}>{labels[document.status]}</span>
        {document.issue && <span className="mt-1 block text-xs text-gray-500">{document.issue}</span>}
      </button>)}
    </div>
  </nav>
}
