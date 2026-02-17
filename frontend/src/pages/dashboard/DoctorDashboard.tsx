// src/pages/DoctorDashboard.tsx
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Upload,
  Users,
  Clock,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react'
import { Card } from '../../components/common/Card'
import { Button } from '../../components/common/Button'
import { useAuthStore } from '../../stores/authStore'
import { usePatientsStore } from '../../stores/patientsStore'
import api from '../../api/api'

// 1. Тип как приходит с бэка
interface ApiRecentUpload {
  id: string
  patient_name: string | null
  file_name: string
  uploaded_at: string
  status: 'pending' | 'processing' | 'done' | 'failed'
  record_id: number | null          // Мед. запись
  patient_id: number | null         // Пациент
}

// 2. Интерфейс для UI
interface RecentUpload {
  id: string
  patientName: string
  documentName: string
  date: string
  status: ApiRecentUpload['status']
  patientId: number | null
}

const DoctorDashboard: React.FC = () => {
  const { user } = useAuthStore()
  const { patients, fetchPatients } = usePatientsStore()

  const [recentUploads, setRecentUploads] = useState<RecentUpload[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // patients
  useEffect(() => {
    fetchPatients()
  }, [fetchPatients])

  // recent uploads
  useEffect(() => {
    setLoading(true)
    api
      .get<ApiRecentUpload[]>('/recent-uploads/')
      .then((res) => {
        const uploads: RecentUpload[] = res.data.map((job) => ({
          id: job.id,
          patientName: job.patient_name ?? '—',
          documentName: job.file_name,
          date: new Date(job.uploaded_at).toLocaleDateString(),
          status: job.status,
          patientId: job.patient_id,
        }))
        setRecentUploads(uploads)
      })
      .catch((err) => {
        console.error(err)
        setError('Не удалось загрузить список загрузок')
      })
      .finally(() => setLoading(false))
  }, [])

  const getStatusIcon = (status: RecentUpload['status']) => {
    switch (status) {
      case 'done':
        return <CheckCircle className="h-5 w-5 text-success-500" />
      case 'processing':
        return <Clock className="h-5 w-5 text-warning-500" />
      case 'failed':
        return <AlertTriangle className="h-5 w-5 text-error-500" />
      default:
        return null
    }
  }

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, Dr. {user?.last_name}
        </h1>
        <p className="mt-1 text-gray-500">
          Here's what's happening with your patients today.
        </p>
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } }}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8"
      >
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card
            icon={<Upload className="h-5 w-5" />}
            title="Upload Archive"
            hoverable
            onClick={() => (window.location.href = '/upload')}
            className="h-full"
          >
            <p className="text-gray-500 mb-4">
              Upload and process new patient medical records
            </p>
            <Button variant="primary" size="sm">
              Upload Files
            </Button>
          </Card>
        </motion.div>

        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card
            icon={<Users className="h-5 w-5" />}
            title="Patient List"
            hoverable
            onClick={() => (window.location.href = '/patients')}
            className="h-full"
          >
            <p className="text-gray-500 mb-4">
              View and manage your {patients.length} patients
            </p>
            <Button variant="outline" size="sm">
              See All Patients
            </Button>
          </Card>
        </motion.div>

        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card icon={<Clock className="h-5 w-5" />} title="Pending Requests" hoverable className="h-full">
            <p className="text-gray-500 mb-4">
              You have 3 pending role requests to review
            </p>
            <Button variant="outline" size="sm">
              Review Requests
            </Button>
          </Card>
        </motion.div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>
        <Card title="Recent Uploads">
          {error && <p className="text-red-600 mb-2">{error}</p>}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Document
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                      Loading…
                    </td>
                  </tr>
                ) : recentUploads.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                      No uploads yet
                    </td>
                  </tr>
                ) : (
                  recentUploads.map((u) => (
                    <tr key={u.id} className="hover:bg-gray-50 transition-colors duration-200">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{u.patientName}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">{u.documentName}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">{u.date}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm">
                          {getStatusIcon(u.status)}
                          <span className="ml-1.5 capitalize">{u.status}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {u.patientId != null ? (
                          <Link to={`/patients/${u.patientId}`} className="text-primary-600 hover:text-primary-900">
                            View Patient
                          </Link>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}

export default DoctorDashboard
