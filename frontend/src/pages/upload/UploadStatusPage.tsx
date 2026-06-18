import React, { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, CheckCircle, FileText } from 'lucide-react'

import { Card } from '../../components/common/Card'
import { useUploadStore } from '../../stores/uploadStore'

const POLL_INTERVAL = 3000

const statusLabel: Record<string, string> = {
  queued: 'В очереди',
  running: 'Обработка',
  completed: 'Завершено',
  completed_with_warnings: 'Завершено с предупреждениями',
  failed: 'Ошибка',
}

const UploadStatusPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const { currentJob, getJobById } = useUploadStore()
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    async function fetchStatus() {
      if (jobId) await getJobById(jobId)
    }
    void fetchStatus()

    timerRef.current = window.setInterval(async () => {
      if (!currentJob) return
      if (['completed', 'completed_with_warnings', 'failed'].includes(currentJob.status)) {
        if (timerRef.current !== null) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        return
      }
      await fetchStatus()
    }, POLL_INTERVAL)

    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current)
    }
  }, [jobId, getJobById, currentJob?.status])

  if (!currentJob) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-gray-500">Загрузка статуса импорта…</p>
      </div>
    )
  }

  const isDone = currentJob.status === 'completed' || currentJob.status === 'completed_with_warnings'
  const isFailed = currentJob.status === 'failed'
  const icon = isDone ? (
    <CheckCircle className="h-16 w-16 text-success-500" />
  ) : isFailed ? (
    <AlertTriangle className="h-16 w-16 text-error-500" />
  ) : (
    <FileText className="h-16 w-16 text-primary-500" />
  )

  const reportEntries = Object.entries(currentJob.report_json ?? {})

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Link to="/upload" className="mb-2 flex items-center text-sm text-primary-600 hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к загрузке
        </Link>
        <h1 className="text-2xl font-bold">Статус импорта</h1>
        <p className="text-gray-500">Архив сохранён; обработка содержимого будет расширена позже.</p>
      </motion.div>

      <Card>
        <div className="flex flex-col items-center md:flex-row md:items-start">
          <div className="p-4">{icon}</div>
          <div className="text-center md:ml-6 md:text-left">
            <h3 className="text-lg font-medium">{statusLabel[currentJob.status] ?? currentJob.status}</h3>
            <p className="text-gray-500">{String(currentJob.report_json?.message ?? 'Ожидание обработки')}</p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <Info label="Файл" value={currentJob.original_filename ?? currentJob.file?.name ?? '—'} />
              <Info label="Размер" value={currentJob.size_bytes ? `${Math.ceil(currentJob.size_bytes / 1024)} КБ` : '—'} />
              <Info label="Загружено" value={new Date(currentJob.created_at).toLocaleString()} />
              {currentJob.finished_at && <Info label="Завершено" value={new Date(currentJob.finished_at).toLocaleString()} />}
            </div>
          </div>
        </div>
      </Card>

      {reportEntries.length > 0 && (
        <Card title="Отчёт">
          <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {reportEntries.map(([key, value]) => (
              <div key={key} className="rounded-lg bg-gray-50 px-3 py-2">
                <dt className="text-xs text-gray-500">{key}</dt>
                <dd className="break-words text-sm font-medium text-gray-900">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-gray-100 px-3 py-2">
      <p className="text-gray-500">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  )
}

export default UploadStatusPage
