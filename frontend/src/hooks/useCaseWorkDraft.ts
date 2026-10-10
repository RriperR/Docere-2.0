import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import api from '../api/api'
import { caseError } from '../api/cases'
import { useUnsavedWork } from './useUnsavedWork'

export interface WorkDraftContent {
  text: string; findings: string; next_actions: string; record_ids: string[]
  parent_id: string | null; opinion_id: string | null; assignee_id: string | null
  attachment_id: string | null; idempotency_key: string | null
}
export const emptyWorkDraft: WorkDraftContent = { text: '', findings: '', next_actions: '', record_ids: [],
  parent_id: null, opinion_id: null, assignee_id: null, attachment_id: null, idempotency_key: null }
interface WorkDraft { version: number; content: WorkDraftContent; updated_at: string | null; expires_at: string | null }
type Kind = 'message' | 'opinion' | 'conclusion'

/** Сериализует autosave, сохраняет текст при конфликте и восстанавливает только личную форму. */
export function useCaseWorkDraft(caseId: string, kind: Kind, enabled: boolean, content: WorkDraftContent,
  restore: (content: WorkDraftContent) => void, paused = false) {
  const [ready, setReady] = useState(!enabled)
  const [saved, setSaved] = useState(JSON.stringify(emptyWorkDraft))
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const version = useRef(0)
  const baseline = useRef(saved)
  const current = useRef(content)
  const onRestore = useRef(restore)
  current.current = content; onRestore.current = restore
  const active = useRef(enabled)
  active.current = enabled
  const inFlight = useRef<Promise<boolean> | null>(null)
  const blocked = useRef(false)
  const endpoint = `/cases/${caseId}/work-drafts/${kind}`
  const load = useCallback(async (signal?: AbortSignal) => {
    setReady(false); setError('')
    try {
      const result = (await api.get<WorkDraft>(endpoint, { signal })).data
      if (signal?.aborted) return
      version.current = result.version
      const next = { ...emptyWorkDraft, ...result.content }
      baseline.current = JSON.stringify(next); setSaved(baseline.current)
      onRestore.current(next); blocked.current = false; setConflict(false)
      setStatus(result.updated_at ? 'Личный черновик восстановлен' : 'Черновик сохраняется только для вас')
      setReady(true)
    } catch (cause) { if (!signal?.aborted) { setError(caseError(cause)); setStatus('Не удалось восстановить черновик') } }
  }, [endpoint])
  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    void load(controller.signal)
    return () => { controller.abort() }
  }, [enabled, load])
  const save = useCallback(async (): Promise<boolean> => {
    while (inFlight.current) { if (!await inFlight.current) return false }
    if (!active.current || blocked.current) return false
    const snapshot = JSON.stringify(current.current)
    if (snapshot === baseline.current) return true
    const value = current.current
    const operation = (async () => {
      setStatus('Сохраняем черновик…'); setError('')
      try {
        const result = (await api.put<WorkDraft>(endpoint, { version: version.current, content: value })).data
        if (!active.current) return false
        version.current = result.version; baseline.current = snapshot; setSaved(snapshot)
        setStatus('Черновик сохранён · только для вас')
        return true
      } catch (cause) {
        if (axios.isAxiosError(cause) && cause.response?.status === 409) {
          blocked.current = true; setConflict(true)
          setError('Черновик изменился в другой вкладке. Ваш текст остаётся в форме; перечитайте сохранённую версию для продолжения.')
        } else setError(caseError(cause))
        setStatus('Последние изменения не сохранены')
        return false
      } finally { inFlight.current = null }
    })()
    inFlight.current = operation
    return operation
  }, [endpoint])
  const snapshot = JSON.stringify(content)
  const dirty = enabled && ready && snapshot !== saved
  useUnsavedWork(dirty)
  useEffect(() => {
    if (!dirty || conflict || paused) return
    const timer = window.setTimeout(() => { void save() }, 700)
    return () => window.clearTimeout(timer)
  }, [dirty, conflict, snapshot, save, paused])
  const reload = async () => {
    if (dirty && !window.confirm('Заменить текст формы сохранённой версией? Последние изменения будут потеряны.')) return
    await load()
  }
  return { ready, status: dirty && !error && status !== 'Сохраняем черновик…' ? 'Последние изменения ещё не сохранены' : status,
    error, conflict, dirty, flush: save, reload, refresh: load }
}
