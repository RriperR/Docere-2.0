type ImportProvenancePanelProps = {
  payloadJson: Record<string, unknown>
}

export const ImportProvenancePanel = ({ payloadJson }: ImportProvenancePanelProps) => {
  const provenance = getImportProvenance(payloadJson)
  if (!provenance) return null

  return (
    <details className="rounded-xl border border-primary-100 bg-primary-50 px-4 py-3">
      <summary className="cursor-pointer text-sm font-medium text-primary-700">Источник и сведения об импорте</summary>
      <div className="mt-2 grid gap-2 text-sm text-primary-900 md:grid-cols-3">
        <div>
          <span className="block text-xs text-primary-600">Архив</span>
          <span className="font-medium">{provenance.sourceArchive && provenance.sourceArchive !== 'documents.zip' ? provenance.sourceArchive : 'Загруженные документы'}</span>
        </div>
        <div>
          <span className="block text-xs text-primary-600">Файлов</span>
          <span className="font-medium">{provenance.filesCount}</span>
        </div>
        <div>
          <span className="block text-xs text-primary-600">Задание импорта</span>
          <span className="font-mono text-xs">{provenance.importJobId}</span>
        </div>
      </div>
    </details>
  )
}

const getImportProvenance = (payloadJson: Record<string, unknown>) => {
  const raw = payloadJson.import_provenance
  if (!raw || typeof raw !== 'object') return null
  const provenance = raw as Record<string, unknown>
  const files = Array.isArray(provenance.files) ? provenance.files : []
  return {
    sourceArchive: typeof provenance.source_archive === 'string' ? provenance.source_archive : null,
    importJobId: typeof provenance.import_job_id === 'string' ? provenance.import_job_id : '—',
    filesCount: files.length,
  }
}
