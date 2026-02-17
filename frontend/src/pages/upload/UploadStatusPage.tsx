// src/pages/upload/UploadStatusPage.tsx
import React, { useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  CheckCircle,
  AlertTriangle,
  FileText,
  ArrowLeft,
} from 'lucide-react'
import { Card } from '../../components/common/Card'
import { useUploadStore } from '../../stores/uploadStore'

const POLL_INTERVAL = 3000

const FIELD_LABELS: Record<string, string> = {
  fios:   'ФИО',
  dobs:   'Даты рождения',
  phones: 'Телефоны',
  emails: 'Email-адреса',
}

const UploadStatusPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const { currentJob, getJobById } = useUploadStore()
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    async function fetchStatus() {
      if (jobId) await getJobById(jobId)
    }
    fetchStatus()

    timerRef.current = window.setInterval(async () => {
      if (!currentJob) return
      if (currentJob.status === 'done' || currentJob.status === 'failed') {
        if (timerRef.current !== null) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        return
      }
      await fetchStatus()
    }, POLL_INTERVAL)

    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
      }
    }
  }, [jobId, getJobById, currentJob?.status])

  if (!currentJob) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Loading job status…</p>
      </div>
    )
  }

  // Деструктурируем поля в snake_case, как они приходят из API
  const {
    file,
    status,
    log,
    raw_extracted,
    uploaded_at,
    completed_at,
    patient_id,
  } = currentJob

  const isDone = status === 'done'
  const isFailed = status === 'failed'
  const isProcessing = status === 'processing'

  const statusIcon = isDone ? (
    <CheckCircle className="h-16 w-16 text-success-500" />
  ) : isFailed ? (
    <AlertTriangle className="h-16 w-16 text-error-500" />
  ) : (
    <FileText className="h-16 w-16 text-primary-500" />
  )

  const statusTitle = isDone
    ? 'Processing Complete'
    : isFailed
    ? 'Processing Failed'
    : isProcessing
    ? 'Processing…'
    : 'Pending'

  const statusDesc = isDone
    ? 'The file was processed successfully.'
    : isFailed
    ? `Processing failed: ${log ?? 'Unknown error'}`
    : isProcessing
    ? 'Your file is being processed…'
    : 'Waiting to start.'

  const fileName = file?.name ?? '—'
  const uploadedLabel = new Date(uploaded_at).toLocaleString()
  const completedLabel = completed_at
    ? new Date(completed_at).toLocaleString()
    : null

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Link
          to="/upload"
          className="flex items-center text-sm text-primary-600 hover:underline mb-2"
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Upload
        </Link>
        <h1 className="text-2xl font-bold">Upload Status</h1>
        <p className="text-gray-500">
          Track your file and review extracted info.
        </p>
      </motion.div>

      <Card>
        <div className="flex flex-col md:flex-row items-center md:items-start">
          <div className="p-4">{statusIcon}</div>
          <div className="md:ml-6 text-center md:text-left">
            <h3 className="text-lg font-medium">{statusTitle}</h3>
            <p className="text-gray-500">{statusDesc}</p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <div className="bg-gray-100 px-3 py-2 rounded">
                <p className="text-gray-500">File</p>
                <p className="font-medium">{fileName}</p>
              </div>
              <div className="bg-gray-100 px-3 py-2 rounded">
                <p className="text-gray-500">Uploaded</p>
                <p className="font-medium">{uploadedLabel}</p>
              </div>
              {completedLabel && (
                <div className="bg-gray-100 px-3 py-2 rounded">
                  <p className="text-gray-500">Completed</p>
                  <p className="font-medium">{completedLabel}</p>
                </div>
              )}
              {patient_id != null && (
                <div className="bg-gray-100 px-3 py-2 rounded">
                  <p className="text-gray-500">Patient</p>
                  <Link
                    to={`/patients/${patient_id}`}
                    className="font-medium text-primary-600 hover:underline"
                  >
                    View Patient Details
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>

      {isDone && raw_extracted && (
        <Card title="Extracted Information">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(raw_extracted).map(([key, values]) => (
              <div key={key}>
                <p className="text-sm font-medium text-gray-500">
                  {FIELD_LABELS[key] ?? key}
                </p>
                {values.length > 0 ? (
                  <ul className="list-disc list-inside">
                    {values.map((v, i) => (
                      <li key={i} className="text-gray-900">
                        {v}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-gray-500">—</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

export default UploadStatusPage
