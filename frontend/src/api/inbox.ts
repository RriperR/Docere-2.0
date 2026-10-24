import type { Page } from './cases'
import api from './api'
export type TaskKind = 'invitation' | 'opinion_requested' | 'share_request' | 'import_review'
export interface InboxTask { key: string; kind: TaskKind; id: string; case_id: string | null; actor_name: string | null; context: string | null; created_at: string }
export const taskLabels: Record<TaskKind, string> = { invitation: 'Приглашение в разбор', opinion_requested: 'Запрос мнения', share_request: 'Доступ к записям', import_review: 'Документы на проверке' }
export const taskActions: Record<TaskKind, string> = { invitation: 'Рассмотреть приглашение', opinion_requested: 'Ответить коллеге', share_request: 'Рассмотреть доступ', import_review: 'Проверить материалы' }
export function taskPath(task: InboxTask): string {
  if (task.kind === 'import_review') return `/upload/review/${task.id}`
  if (task.kind === 'share_request') return `/share-requests?request=${task.id}`
  return `/cases/${task.case_id}${task.kind === 'opinion_requested' ? `?tab=review&opinion=${task.id}` : ''}`
}
export async function getTasks(offset: number, limit: number, kind: string, signal: AbortSignal) {
  return (await api.get<Page<InboxTask>>('/inbox/tasks', { params: { offset, limit, ...(kind !== 'all' ? { kind } : {}) }, signal })).data
}
