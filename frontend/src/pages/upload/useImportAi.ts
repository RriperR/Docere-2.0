import { requestId } from '../../utils/requestId'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiActive, AiCapabilities, AiRun, cancelAiRun, getAiCapabilities, getAiRun, startAiRun, importAiError, listAiRuns } from '../../api/importAi'
import axios from 'axios'
import { UploadJob, useUploadStore } from '../../stores/uploadStore'

export function useImportAi(job: UploadJob | null) {
  const [capabilities, setCapabilities] = useState<AiCapabilities | null>(null)
  const [run, setRun] = useState<AiRun | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<AiRun[]>([])
  const [hasOlder, setHasOlder] = useState(false)
  const refreshJob = useUploadStore(s => s.getJobById)
  const pendingKey = useRef<{ selection: string; key: string } | null>(null)
  const generation = useRef(0)
  const jobId = job?.id
  const runId = run?.id ?? job?.report_json.latest_ai_run_id
  const automatic = job?.report_json.ai_requested === true
  const active = run ? aiActive(run.status) : Boolean(runId || automatic)
  useEffect(() => {
    generation.current += 1
    setRun(null); setHistory([]); setHasOlder(false); setError(''); setBusy(false); pendingKey.current = null
  }, [jobId])
  useEffect(() => {
    const controller = new AbortController()
    void getAiCapabilities(controller.signal).then(value => { if (!controller.signal.aborted) setCapabilities(value) }).catch(e => { if (!controller.signal.aborted) setError(importAiError(e)) })
    return () => controller.abort()
  }, [jobId])
  useEffect(() => {
    if (!jobId) return
    const controller = new AbortController()
    let fetching = false
    const refresh = async () => {
      if (document.hidden || fetching) return
      fetching = true
      try {
        if (runId) {
          const result = await getAiRun(jobId, runId, controller.signal)
          if (!controller.signal.aborted) { setRun(result); setHistory(prev => prev.map(item => item.id === result.id ? result : item)); setError('') }
        } else if (automatic) await refreshJob(jobId)
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(importAiError(e))
          if (axios.isAxiosError(e) && [401, 403, 404].includes(e.response?.status ?? 0)) {
            setRun(null); setHistory([])
            await refreshJob(jobId)
          }
        }
      }
      finally { fetching = false }
    }
    void refresh()
    const timer = active ? window.setInterval(() => void refresh(), 3000) : undefined
    const focus = () => void refresh()
    window.addEventListener('focus', focus); document.addEventListener('visibilitychange', focus)
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener('focus', focus); document.removeEventListener('visibilitychange', focus) }
  }, [jobId, runId, active, automatic, refreshJob])
  useEffect(() => {
    if (!jobId) return
    const controller = new AbortController()
    void listAiRuns(jobId, 0, controller.signal).then(items => {
      if (!controller.signal.aborted) { setHistory(items); setHasOlder(items.length === 5) }
    }).catch(e => { if (!controller.signal.aborted) setError(importAiError(e)) })
    return () => controller.abort()
  }, [jobId, job?.report_json.latest_ai_run_id])
  const loadOlder = async () => {
    if (!jobId) return
    const current = generation.current
    try { const items = await listAiRuns(jobId, history.length); if (current === generation.current) { setHistory(prev => [...prev, ...items]); setHasOlder(items.length === 5) } }
    catch (e) { if (current === generation.current) setError(importAiError(e)) }
  }
  const start = useCallback(async (fileIds: string[]) => {
    if (!jobId || !job) return
    const current = generation.current
    const selection = fileIds.slice().sort().join(',')
    if (pendingKey.current?.selection !== selection) pendingKey.current = { selection, key: requestId() }
    setBusy(true); setError('')
    try {
      const result = await startAiRun(jobId, fileIds, job.version ?? 1, pendingKey.current.key)
      if (generation.current === current) { setRun(result); setHistory(prev => [result, ...prev.filter(item => item.id !== result.id)]); pendingKey.current = null }
    } catch (e) { if (generation.current === current) setError(importAiError(e)) }
    finally { if (generation.current === current) setBusy(false) }
  }, [job, jobId])
  const cancel = useCallback(async () => {
    if (!jobId || !run) return
    const current = generation.current
    try { const result = await cancelAiRun(jobId, run.id); if (generation.current === current) setRun(result) }
    catch (e) { if (generation.current === current) setError(importAiError(e)) }
  }, [jobId, run])
  return { capabilities, run, history, hasOlder, loadOlder, selectRun: setRun, error, busy, active: run ? aiActive(run.status) : automatic, start, cancel }
}
