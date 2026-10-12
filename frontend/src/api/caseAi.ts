import api from './api'
import type { Material, Page } from './cases'
export interface SummarySource { page: number; excerpt: string }
export interface SummaryFact { text: string; category: 'fact' | 'mentioned_care'; sources: SummarySource[] }
export interface SummaryDocument {
  record_id: string; attachment_id: string | null; title: string; record_date: string; filename: string; mime_type: string
  status: string; facts: SummaryFact[]; issues: string[]; document_date: string | null; page_count: number
  checksum: string | null; error_code: string | null
}
export interface CaseSummaryRun {
  id: string; case_id: string; status: string; model: string; provider: string; prompt_version: string
  created_at: string; documents: SummaryDocument[]
}
export interface SummaryCapabilities { enabled: boolean; provider: string; max_documents: number; max_pages: number; max_pages_per_document: number }
export const caseAiApi = {
  capabilities: async (signal?: AbortSignal) => (await api.get<SummaryCapabilities>('/archives/ai-capabilities', { signal })).data,
  materials: async (id: string, offset: number, signal?: AbortSignal) => (await api.get<Page<Material>>(`/cases/${id}/materials`, { params: { offset, limit: 20 }, signal })).data,
  latest: async (id: string, signal?: AbortSignal) => (await api.get<CaseSummaryRun | null>(`/cases/${id}/ai-summary`, { signal })).data,
  start: async (id: string, recordIds: string[], version: number, key: string, signal?: AbortSignal) =>
    (await api.post<CaseSummaryRun>(`/cases/${id}/ai-summary/runs`, { record_ids: recordIds, version, idempotency_key: key, consent: true }, { signal })).data,
  cancel: async (id: string, run: string, signal?: AbortSignal) => (await api.post<CaseSummaryRun>(`/cases/${id}/ai-summary/runs/${run}/cancel`, undefined, { signal })).data,
}
