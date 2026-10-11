import api from './api'
import axios from 'axios'

export type AiFieldName = 'fio' | 'date_of_birth' | 'event_date' | 'record_type' | 'title' | 'clinical_summary'
export interface AiField { value: string; sources: { page: number; excerpt: string }[] }
export interface AiDocument {
  file_id: string; filename: string; path: string; status: string; page_count: number; checksum: string | null
  error_code: string | null; result: { fields?: Partial<Record<AiFieldName, AiField>>; issues?: string[]; patient_conflict?: boolean; multiple_patients?: boolean }
}
export interface AiRun { id: string; job_id: string; status: string; provider: string; model: string; created_at: string; prompt_version: string; documents: AiDocument[] }
export interface AiCapabilities { enabled: boolean; provider: string; model: string; max_documents: number; max_pages: number; max_pages_per_document: number }
export interface AppliedAi { run_id: string; file_id: string; fields: AiFieldName[] }
export const aiActive = (status: string) => ['queued', 'running'].includes(status)
export const getAiCapabilities = async (signal?: AbortSignal) => (await api.get<AiCapabilities>('/archives/ai-capabilities', { signal })).data
export const getAiRun = async (jobId: string, runId: string, signal?: AbortSignal) => (await api.get<AiRun>(`/archives/imports/${jobId}/ai-runs/${runId}`, { signal })).data
export const startAiRun = async (jobId: string, fileIds: string[], version: number, key: string) => (await api.post<AiRun>(`/archives/imports/${jobId}/ai-runs`, { file_ids: fileIds, version, idempotency_key: key })).data
export const cancelAiRun = async (jobId: string, runId: string) => (await api.post<AiRun>(`/archives/imports/${jobId}/ai-runs/${runId}/cancel`)).data
export const aiErrorLabels: Record<string, string> = {
  ai_unavailable: 'AI-сервис ещё не настроен. Можно продолжить импорт вручную.',
  provider_authentication: 'Провайдер отклонил серверный ключ. Проверьте настройки подключения.',
  configuration_changed: 'Настройки модели изменились. Запустите новый анализ.',
  provider_unavailable: 'AI-сервис временно недоступен. Можно повторить анализ.',
  provider_request_rejected: 'Провайдер не принял запрос. Проверьте поддержку изображений у модели.',
  invalid_response: 'Ответ AI не прошёл проверку. Предложения не применены.',
  incomplete_response: 'Ответ AI оказался неполным. Предложения не применены.',
  document_limit: 'Превышен лимит документов. Выберите меньше файлов.',
  document_page_limit: 'Слишком много страниц в документе. Анализ не выполнялся.',
  page_limit: 'Превышен общий лимит страниц. Запустите этот документ отдельно.',
  unreadable_document: 'Документ не читается или защищён паролем. Можно продолжить вручную.',
  image_size_limit: 'Изображение превышает допустимые размеры.',
  processing_error: 'Не удалось обработать документ. Можно повторить анализ.',
  analysis_running: 'Анализ этого импорта уже выполняется.',
  review_conflict: 'Черновик изменился. Обновите данные, сохранив свои правки.',
  invalid_ai_source: 'Источники предложения не соответствуют выбранному документу.',
  patient_identity_confirmation_required: 'Подтвердите принадлежность документов выбранному пациенту.',
  multiple_patients_document: 'В документе обнаружены разные пациенты. Пропустите его и загрузите раздельные документы.',
  cancelled: 'Обработка отменена.',
}
export const aiFieldLabels: Record<AiFieldName, string> = { fio: 'ФИО', date_of_birth: 'Дата рождения', event_date: 'Дата события', record_type: 'Тип записи', title: 'Название', clinical_summary: 'Клиническое описание' }
export function aiIssueLabel(issue: string) {
  const [kind, name] = issue.split(':')
  const label = aiFieldLabels[name as AiFieldName]
  return label && kind === 'missing' ? `${label}: не найдено` : label && kind === 'conflicting' ? `${label}: противоречащие сведения` : issue
}

export function importAiError(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail.code === 'string') return aiErrorLabels[detail.code] ?? 'Не удалось выполнить AI-анализ.'
    if ([401, 403, 404].includes(error.response?.status ?? 0)) return 'Доступ к импорту утрачен.'
  }
  return 'Не удалось получить состояние AI. Повторите запрос.'
}

export const listAiRuns = async (jobId: string, offset = 0, signal?: AbortSignal) => (await api.get<AiRun[]>(`/archives/imports/${jobId}/ai-runs`, { params: { offset, limit: 5 }, signal })).data
