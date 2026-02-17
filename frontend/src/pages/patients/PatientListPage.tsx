// src/pages/PatientListPage.tsx
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, Calendar, FileText, Plus } from 'lucide-react'
import { format } from 'date-fns'

import { Card } from '../../components/common/Card'
import { Input } from '../../components/common/Input'
import { Button } from '../../components/common/Button'
import { usePatientsStore } from '../../stores/patientsStore'
import api from '../../api/api'

const PatientListPage: React.FC = () => {
  const {
    filteredPatients,
    fetchPatients,
    searchPatients,
    filterPatientsByDate,
    isLoading,
    error,
  } = usePatientsStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate]     = useState('')
  const [endDate, setEndDate]         = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  // ---- modal state ----
  const [isModalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState({
    lastName:   '',
    firstName:  '',
    middleName: '',
    email:      '',
    phone:      '',
    birthday:   '',
  })
  const [formError, setFormError]     = useState<string | null>(null)
  const [isSubmitting, setSubmitting] = useState(false)

  const patientsPerPage = 10
  const indexLast  = currentPage * patientsPerPage
  const indexFirst = indexLast - patientsPerPage
  const current    = filteredPatients.slice(indexFirst, indexLast)
  const totalPages = Math.ceil(filteredPatients.length / patientsPerPage)

  useEffect(() => {
    fetchPatients()
  }, [fetchPatients])

  useEffect(() => {
    searchPatients(searchQuery)
    setCurrentPage(1)
  }, [searchQuery, searchPatients])

  useEffect(() => {
    filterPatientsByDate(startDate, endDate)
    setCurrentPage(1)
  }, [startDate, endDate, filterPatientsByDate])

  const changePage = (n: number) => {
    if (n < 1 || n > totalPages) return
    setCurrentPage(n)
  }

  // ---- modal handlers ----
  const openModal  = () => setModalOpen(true)
  const closeModal = () => {
    setModalOpen(false)
    setForm({
      lastName:   '',
      firstName:  '',
      middleName: '',
      email:      '',
      phone:      '',
      birthday:   '',
    })
    setFormError(null)
  }

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleFormSubmit = async () => {
    setFormError(null)
    setSubmitting(true)
    try {
      const payload: any = {
        first_name:  form.firstName,
        middle_name: form.middleName,
        last_name:   form.lastName,
        email:       form.email || null,
        phone:       form.phone || null,
      };
      if (form.birthday.trim()) {
        payload.birthday = form.birthday;  // only include if non-empty
      }
      await api.post('/patients/', payload);
      await fetchPatients()
      closeModal()
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to add patient')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold">Patient List</h1>
          <p className="text-gray-500">View and manage your patients.</p>
        </div>
        <Button
          icon={<Plus className="h-5 w-5" />}
          onClick={openModal}
        >
          Add Patient
        </Button>
      </motion.div>

      {isLoading ? (
        <p className="text-center py-20">Loading patients…</p>
      ) : error ? (
        <p className="text-center py-20 text-red-600">{error}</p>
      ) : (
        <Card>
          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Input
              placeholder="Search patients…"
              icon={<Search className="h-5 w-5" />}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            <Input
              type="date"
              icon={<Calendar className="h-5 w-5" />}
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
            />
            <Input
              type="date"
              icon={<Calendar className="h-5 w-5" />}
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
            />
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {['Patient', 'DOB', 'Last Visit', 'Records', 'Actions'].map(h => (
                    <th
                      key={h}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {current.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                      No patients found.
                    </td>
                  </tr>
                ) : current.map(p => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <div className="h-10 w-10 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-medium">
                          {(p.firstName[0] ?? '') + (p.lastName[0] ?? '')}
                        </div>
                        <div className="ml-4">
                          <div className="font-medium text-gray-900">
                            {p.lastName} {p.firstName} {p.middleName ? p.middleName + ' ' : ''}
                          </div>
                          <div className="text-gray-500 text-sm">{p.email || '—'}</div>
                          {p.phone && (
                            <div className="text-gray-500 text-sm">{p.phone}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {p.birthday
                        ? format(new Date(p.birthday), 'MMM d, yyyy')
                        : '—'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {p.lastVisit
                        ? format(new Date(p.lastVisit), 'MMM d, yyyy')
                        : '—'}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <div className="flex items-center">
                        <FileText className="h-5 w-5 text-gray-400 mr-1" />
                        {p.recordCount ?? 0}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <Link
                        to={`/patients/${p.id}`}
                        className="text-primary-600 hover:underline"
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center px-6 py-3 bg-gray-50 border-t">
              <Button onClick={() => changePage(currentPage - 1)} disabled={currentPage === 1}>
                Previous
              </Button>
              <div className="space-x-1">
                {Array.from({ length: totalPages }, (_, i) => (
                  <Button
                    key={i + 1}
                    variant={currentPage === i + 1 ? 'primary' : 'outline'}
                    onClick={() => changePage(i + 1)}
                  >
                    {i + 1}
                  </Button>
                ))}
              </div>
              <Button onClick={() => changePage(currentPage + 1)} disabled={currentPage === totalPages}>
                Next
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Add Patient Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-semibold mb-4">Add New Patient</h2>
            {formError && <p className="text-red-600 mb-2">{formError}</p>}
            <div className="space-y-4">
              <Input
                name="lastName"
                label="Last Name *"
                value={form.lastName}
                onChange={handleFormChange}
              />
              <Input
                name="firstName"
                label="First Name *"
                value={form.firstName}
                onChange={handleFormChange}
              />
              <Input
                name="middleName"
                label="Middle Name"
                value={form.middleName}
                onChange={handleFormChange}
              />
              <Input
                name="email"
                type="email"
                label="Email"
                value={form.email}
                onChange={handleFormChange}
              />
              <Input
                name="phone"
                label="Phone"
                value={form.phone}
                onChange={handleFormChange}
              />
              <Input
                name="birthday"
                type="date"
                label="Date of Birth"
                value={form.birthday}
                onChange={handleFormChange}
              />
            </div>
            <div className="mt-6 flex justify-end space-x-2">
              <Button variant="outline" onClick={closeModal}>Cancel</Button>
              <Button
                onClick={handleFormSubmit}
                disabled={
                  isSubmitting ||
                  !form.firstName.trim() ||
                  !form.lastName.trim()
                }
              >
                {isSubmitting ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PatientListPage
