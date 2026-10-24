import type { UploadJob } from '../stores/uploadStore'

/** Внутренняя упаковка отдельных файлов не должна выглядеть пользовательским ZIP-архивом. */
export function importTitle(job: Pick<UploadJob, 'original_filename' | 'report_json'>): string {
  if (job.original_filename && job.original_filename !== 'documents.zip') return job.original_filename
  const count = job.report_json?.files_total ?? job.report_json?.patients?.reduce((total, patient) =>
    total + patient.record_groups.reduce((files, group) => files + group.files.length, 0), 0)
  return count ? `Загруженные документы · файлов: ${count}` : 'Загруженные документы'
}

/** Отображаемая подпись задачи не изменяет её адрес или состояние. */
export function importTaskContext(context: string | null): string | null {
  return context === 'documents.zip' ? 'Загруженные документы' : context
}
