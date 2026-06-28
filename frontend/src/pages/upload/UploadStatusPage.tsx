import React, { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, CheckCircle, FileSearch, FileText } from 'lucide-react'

import { Button } from '../../components/common/Button'
import { Card } from '../../components/common/Card'
import { ImportResultSummary } from '../../components/imports/ImportResultSummary'
import { useUploadStore } from '../../stores/uploadStore'
import { groupedWarnings } from '../../utils/importWarnings'

const POLL_INTERVAL = 3000
const FINAL_STATUSES = ['needs_review', 'completed', 'completed_with_warnings', 'failed']

const statusLabel: Record<string, string> = {
  queued: 'В очереди',
  running: 'Обработка',
  needs_review: 'Нужна проверка',
  completed: 'Завершено',
  completed_with_warnings: 'Завершено с предупреждениями',
  failed: 'Ошибка',
}

const UploadStatusPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const { currentJob, getJobById } = useUploadStore()
  const currentJobStatus = currentJob?.status
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!jobId) return undefined

    const fetchStatus = async () => {
      await getJobById(jobId)
    }

    void fetchStatus()
    timerRef.current = window.setInterval(() => {
      if (currentJobStatus && FINAL_STATUSES.includes(currentJobStatus)) {
        if (timerRef.current !== null) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        return
      }
      void fetchStatus()
    }, POLL_INTERVAL)

    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current)
    }
  }, [jobId, getJobById, currentJobStatus])

  if (!currentJob) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-gray-500">Загрузка статуса импорта...</p>
      </div>
    )
  }

  const isDone = currentJob.status === 'completed' || currentJob.status === 'completed_with_warnings'
  const isFailed = currentJob.status === 'failed'
  const needsReview = currentJob.status === 'needs_review'
  const report = currentJob.report_json ?? {}
  const warnings = Array.isArray(report.warnings) ? report.warnings : []
  const warningViews = groupedWarnings(warnings)
  const patients = Array.isArray(report.patients) ? report.patients : []

  const icon = isDone ? (
    <CheckCircle className="h-16 w-16 text-success-500" />
  ) : isFailed ? (
    <AlertTriangle className="h-16 w-16 text-error-500" />
  ) : needsReview ? (
    <FileSearch className="h-16 w-16 text-warning-500" />
  ) : (
    <FileText className="h-16 w-16 text-primary-500" />
  )

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Link to="/upload" className="mb-2 flex items-center text-sm text-primary-600 hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад к загрузке
        </Link>
        <h1 className="text-2xl font-bold">Статус импорта</h1>
        <p className="text-gray-500">Архив разбирается в фоне; найденные данные появятся здесь для проверки.</p>
      </motion.div>

      <Card>
        <div className="flex flex-col items-center gap-4 md:flex-row md:items-start">
          <div className="p-2">{icon}</div>
          <div className="flex-1 text-center md:text-left">
            <h3 className="text-lg font-medium">{statusLabel[currentJob.status] ?? currentJob.status}</h3>
            <p className="text-gray-500">{String(report.message ?? 'Ожидание обработки')}</p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <Info label="Файл" value={currentJob.original_filename ?? currentJob.file?.name ?? '-'} />
              <Info label="Размер" value={currentJob.size_bytes ? `${Math.ceil(currentJob.size_bytes / 1024)} КБ` : '-'} />
              <Info label="Загружено" value={new Date(currentJob.created_at).toLocaleString()} />
              {currentJob.finished_at && <Info label="Завершено" value={new Date(currentJob.finished_at).toLocaleString()} />}
            </div>
            {needsReview && (
              <div className="mt-5">
                <Link to={`/upload/review/${currentJob.id}`}>
                  <Button type="button" icon={<FileSearch className="h-4 w-4" />}>
                    Проверить импорт
                  </Button>
                </Link>
              </div>
            )}
            {isDone && (
              <div className="mt-5">
                <Link to="/patients">
                  <Button type="button" variant="outline">
                    Перейти к пациентам
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <Summary label="Пациенты" value={Number(report.patients_created ?? patients.length ?? 0)} />
        <Summary label="Записи" value={Number(report.records_created ?? countRecords(patients))} />
        <Summary label="Вложения" value={Number(report.attachments_created ?? countFiles(patients))} />
        <Summary label="Предупреждения" value={warnings.length} />
      </div>

      {isDone && <ImportResultSummary patients={report.resolved_patients ?? []} />}

      {warnings.length > 0 && (
        <Card title="Предупреждения" accent="warning">
          <div className="space-y-3 text-sm">
            {warningViews.map((view) => (
              <div key={view.label} className="space-y-2">
                <span className={`rounded border px-2 py-0.5 text-xs font-medium ${view.tone}`}>
                  {view.label}: {view.warnings.length}
                </span>
                <ul className="space-y-1 text-gray-700">
                  {view.warnings.map((warning, index) => (
                    <li key={`${warning}-${index}`} className="break-words">{warning}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      {isFailed && report.errors && Array.isArray(report.errors) && report.errors.length > 0 && (
        <Card title="Причина ошибки" accent="error">
          <div className="space-y-3">
            <ul className="space-y-2 text-sm text-error-700">
              {report.errors.map((item, index) => <li key={`${item}-${index}`}>{String(item)}</li>)}
            </ul>
            <Link to="/upload">
              <Button type="button" variant="outline">Загрузить исправленный архив</Button>
            </Link>
          </div>
        </Card>
      )}
    </div>
  )
}

function countRecords(patients: Array<{ record_groups?: unknown }>) {
  return patients.reduce((sum, patient) => {
    return sum + (Array.isArray(patient.record_groups) ? patient.record_groups.length : 0)
  }, 0)
}

function countFiles(patients: Array<{ record_groups?: unknown }>) {
  return patients.reduce((sum, patient) => {
    if (!Array.isArray(patient.record_groups)) return sum
    return sum + patient.record_groups.reduce((inner, group) => {
      if (!group || typeof group !== 'object' || !('files' in group) || !Array.isArray(group.files)) return inner
      return inner + group.files.length
    }, 0)
  }, 0)
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-gray-100 px-3 py-2">
      <p className="text-gray-500">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  )
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
    </Card>
  )
}

export default UploadStatusPage
