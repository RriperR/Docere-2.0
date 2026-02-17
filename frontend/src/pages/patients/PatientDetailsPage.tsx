// src/pages/patients/PatientDetailsPage.tsx
import React, { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, FileText, X, Plus, User } from 'lucide-react'
import { format } from 'date-fns'
import { useDropzone } from 'react-dropzone'
import api from '../../api/api'

import { Card } from '../../components/common/Card'
import { Button } from '../../components/common/Button'
import { Tabs } from '../../components/common/Tabs'
import { AddRecordModal } from '../../components/AddRecordModal'

import {
  usePatientsStore,
  PatientRecord,
  DoctorInfo,
} from '../../stores/patientsStore'

type TabId = 'history' | 'files' | 'audit'
const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'history', label: 'Medical History', icon: <FileText className="h-4 w-4" /> },
  { id: 'files',   label: 'Files',           icon: <FileText className="h-4 w-4" /> },
  { id: 'audit',   label: 'Audit Log',       icon: <FileText className="h-4 w-4" /> },
]

export default function PatientDetailsPage() {
  const { id } = useParams<{ id: string }>()
  const {
    currentPatient,
    patientRecords,
    isLoading,
    error,
    fetchPatientById,
    fetchPatientRecords,
    updatePatientRecord,
  } = usePatientsStore()

  const [activeTab, setActiveTab]       = useState<TabId>('history')
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingId, setEditingId]       = useState<string | null>(null)
  const [selected, setSelected]         = useState<Set<string>>(new Set())
  const [shareAllMode, setShareAllMode] = useState(false)

  useEffect(() => {
    if (id) {
      void fetchPatientById(id)
      void fetchPatientRecords(id)
    }
  }, [id])

  const toggleSelect = (recId: string) => {
    setSelected(s => {
      const nxt = new Set(s)
      nxt.has(recId) ? nxt.delete(recId) : nxt.add(recId)
      return nxt
    })
  }

  const shareSelected = async (email: string) => {
    // отправляем запрос на шаринг
    await api.post('/share-requests/', {
      patient_id: Number(id),
      to_email: email,
      record_ids: Array.from(selected),
    })
    // сброс
    setSelected(new Set())
  }

  if (isLoading && !currentPatient) {
    return <p className="text-center mt-8 text-gray-500">Loading…</p>
  }
  if (error) {
    return <p className="text-center mt-8 text-red-600">{error}</p>
  }
  if (!currentPatient) return null

  return (
    <div className="space-y-8">
      {/* HEADER */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Link
          to="/patients"
          className="inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700 mb-4"
        >
          <ArrowLeft className="mr-1 h-4 w-4" /> Back to Patient List
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {currentPatient.firstName} {currentPatient.lastName}
            </h1>
            <p className="text-gray-500">Patient ID: {currentPatient.id}</p>
          </div>
          <div className="flex items-center space-x-4">
            <Button variant="primary" onClick={() => setShowAddModal(true)}>
              Add Record
            </Button>
          </div>
        </div>
      </motion.div>

      {showAddModal && (
        <AddRecordModal
          patientId={id!}
          onClose={() => {
            setShowAddModal(false)
            void fetchPatientRecords(id!)
          }}
        />
      )}

      {/* INFO CARDS */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
      >
        <Card icon={<User className="h-5 w-5" />} title="Personal Information">
          <div className="space-y-4">
            {[
              ['Date of Birth', currentPatient.birthday],
              ['Email',         currentPatient.email],
              ['Phone',         currentPatient.phone],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-sm font-medium text-gray-500">{label}</p>
                <p className="mt-1">{value || '—'}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card icon={<FileText className="h-5 w-5" />} title="Medical Records">
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-500">Total Records</p>
              <p className="mt-1 text-2xl font-bold text-primary-600">{patientRecords.length}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Last Updated</p>
              <p className="mt-1">{currentPatient.lastVisit || 'No records'}</p>
            </div>
          </div>
        </Card>

        <Card icon={<User className="h-5 w-5" />} title="Recent Activity">
          <div className="space-y-4">
            {patientRecords.slice(0, 3).map(rec => (
              <div key={rec.id} className="text-sm">
                <p className="font-medium">{rec.notes || 'Record'}</p>
                <p className="text-gray-500">{rec.visit_date || '—'}</p>
              </div>
            ))}
          </div>
        </Card>
      </motion.div>

      {/* TABS */}
      <Card>
        <Tabs
          tabs={tabs}
          defaultTab="history"
          onChange={t => setActiveTab(t as TabId)}
          className="mb-6"
        />

        {activeTab === 'history' && (
          <>
            {selected.size > 0 && (
              <div className="mb-4 flex justify-end">
                <Button variant="primary" onClick={() => setShareAllMode(true)}>
                  Share selected ({selected.size})
                </Button>
              </div>
            )}
            <div className="space-y-6">
              {patientRecords.map(rec => (
                <HistoryItem
                  key={rec.id}
                  rec={rec}
                  selectable
                  checked={selected.has(rec.id)}
                  onToggle={() => toggleSelect(rec.id)}
                  isEditing={editingId === rec.id}
                  onEdit={() => setEditingId(rec.id)}
                  onCancel={() => setEditingId(null)}
                  onSave={async form => {
                    if (id) await updatePatientRecord(id, rec.id, form)
                    setEditingId(null)
                    if (id) void fetchPatientRecords(id)
                  }}
                />
              ))}
            </div>
          </>
        )}

        {activeTab === 'files' && <p className="text-center text-gray-500 py-10">Здесь файлы…</p>}
        {activeTab === 'audit' && <p className="text-center text-gray-500 py-10">Audit Log…</p>}
      </Card>

      {shareAllMode && (
        <BulkShareModal
          count={selected.size}
          onCancel={() => setShareAllMode(false)}
          onSend={async email => {
            await shareSelected(email)
            setShareAllMode(false)
          }}
        />
      )}
    </div>
  )
}

interface HistoryItemProps {
  rec: PatientRecord
  selectable?: boolean
  checked?: boolean
  onToggle?: () => void
  isEditing: boolean
  onEdit: () => void
  onCancel: () => void
  onSave: (form: FormData) => Promise<void>
}

function HistoryItem({
  rec,
  selectable,
  checked,
  onToggle,
  isEditing,
  onEdit,
  onCancel,
  onSave,
}: HistoryItemProps) {
  const isImage = (name: string) => /\.(jpe?g|png|gif)$/i.test(name)
  const existing = rec.lab_files || []
  const [expanded, setExpanded] = useState(false)
  const [visitDate, setVisitDate] = useState(rec.visit_date || '')
  const [location, setLocation]   = useState(rec.appointment_location || '')
  const [notes, setNotes]         = useState(rec.notes)
  const [files, setFiles]         = useState<File[]>([])
  const [toDelete, setToDelete]   = useState<string[]>([])
  const [error, setError]         = useState<string|null>(null)

  const { getRootProps, getInputProps } = useDropzone({
    onDrop: useCallback((acc: File[]) => setFiles(f => [...f, ...acc]), []),
    multiple: true,
    accept: { 'image/*': [], 'application/pdf': [] },
  })

  const doc = rec.doctor as DoctorInfo|undefined
  const dateLabel = rec.visit_date
    ? format(new Date(rec.visit_date), 'd MMMM yyyy')
    : '—'

  // VIEW
  if (!isEditing) {
    return (
      <div className="flex border rounded-lg overflow-hidden mb-4">
        {selectable && (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            className="m-4 self-start"
          />
        )}
        <div className="flex-1">
          <div className="grid grid-cols-[auto_1fr_auto_auto] items-center bg-gray-50 px-6 py-2 text-sm text-gray-600">
            <div>{dateLabel}</div>
            <div className="text-center">Комментарий / Заключение</div>
            <div className="text-right">Лабораторные данные</div>
            <button
              onClick={onEdit}
              className="ml-4 px-2 py-1 bg-primary-600 text-white text-xs rounded"
            >Edit</button>
          </div>
          <div className="grid grid-cols-[auto_auto_2fr_1fr] gap-6 p-6">
            {/* Doctor */}
            <div className="flex flex-col items-center space-y-1">
              <img src={doc?.photo||'/images/doctor.png'} className="h-10 w-10 rounded-full" />
              <p className="font-medium">{doc?.full_name || 'Doctor not assigned'}</p>
              <p className="text-xs text-gray-500">{doc?.specialization||'No specialization'}</p>
            </div>
            {/* Location */}
            <div className="flex flex-col items-center space-y-1">
              <img src="/images/hospital.png" className="h-10 w-10 rounded-full" />
              <p className="font-medium">{rec.appointment_location||'Location not provided'}</p>
            </div>
            {/* Notes */}
            <div className="text-gray-800">
              {expanded ? rec.notes : rec.notes.slice(0,200)+'…'}
              {rec.notes.length>200 && (
                <button onClick={()=>setExpanded(x=>!x)} className="text-primary-600 ml-2 text-sm">
                  {expanded?'Show less':'Read more'}
                </button>
              )}
            </div>
            {/* Files */}
            <div className="flex flex-wrap gap-3">
              {existing.map(f =>
                isImage(f.file)
                  ? <a key={f.id} href={f.file} className="h-24 w-24 overflow-hidden rounded border"><img src={f.file} className="h-full w-full object-cover"/></a>
                  : <a key={f.id} href={f.file} className="h-24 w-24 rounded border flex flex-col items-center justify-center bg-gray-50 text-primary-600">
                      <FileText className="h-8 w-8"/><span className="text-[10px] mt-1">PDF</span>
                    </a>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // EDIT
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!visitDate && !location && !notes && files.length===0 && toDelete.length===0) {
      setError('Заполните хотя бы одно поле или измените файлы')
      return
    }
    const form = new FormData()
    if (visitDate) form.append('visit_date', visitDate)
    if (location)  form.append('appointment_location', location)
    if (notes)     form.append('notes', notes)
    toDelete.forEach(id => form.append('delete_file_ids', id))
    files.forEach(f => form.append('files', f))
    await onSave(form)
  }

  return (
    <form onSubmit={handleSave} className="border rounded-lg overflow-hidden bg-gray-50 mb-4">
      {error && <p className="text-red-600 m-4">{error}</p>}
      {/* HEADER */}
      <div className="grid grid-cols-[auto_1fr_auto] bg-gray-100 px-6 py-2 text-sm text-gray-600">
        <input
          type="date"
          value={visitDate}
          onChange={e=>setVisitDate(e.target.value)}
          className="border rounded p-1 text-sm w-full focus:ring-primary-500"
        />
        <div className="text-center">Комментарий / Заключение</div>
        <div className="flex justify-end space-x-2">
          <button type="button" onClick={onCancel} className="px-2 py-1 border rounded">Cancel</button>
          <Button type="submit" size="sm">Save</Button>
        </div>
      </div>
      {/* CONTENT */}
      <div className="grid grid-cols-[auto_auto_2fr_1fr] gap-6 p-6">
        {/* Doctor */}
        <div className="flex flex-col items-center space-y-1">
          <img src={doc?.photo||'/images/doctor.png'} className="h-10 w-10 rounded-full" />
          <input readOnly value={doc?.full_name||''} className="border rounded p-1 text-xs text-center w-full" />
        </div>
        {/* Location */}
        <div className="flex flex-col items-center space-y-1">
          <img src="/images/hospital.png" className="h-10 w-10 rounded-full"/>
          <input
            value={location}
            onChange={e=>setLocation(e.target.value)}
            placeholder="Location"
            className="border rounded p-1 text-sm w-full text-center"
          />
        </div>
        {/* Notes */}
        <textarea
          value={notes}
          onChange={e=>setNotes(e.target.value)}
          rows={3}
          placeholder="Комментарий"
          className="border rounded p-1 text-sm w-full"
        />
        {/* Files */}
        <div className="flex flex-wrap gap-3">
          {existing.map(f => !toDelete.includes(f.id) && (
            <div key={f.id} className="relative h-24 w-24 border rounded overflow-hidden">
              <button type="button" onClick={()=>setToDelete(prev=>[...prev,f.id])}
                className="absolute top-1 right-1 bg-white rounded-full p-0.5">
                <X className="h-4 w-4 text-red-500"/>
              </button>
              {isImage(f.file)
                ? <img src={f.file} className="h-full w-full object-cover"/>
                : <div className="flex flex-col items-center justify-center h-full bg-gray-50 text-primary-600">
                    <FileText className="h-8 w-8"/><span className="text-[10px] mt-1">PDF</span>
                  </div>
              }
            </div>
          ))}
          {files.map((f,i)=>
            <div key={i} className="relative h-24 w-24 border rounded overflow-hidden">
              <button type="button" onClick={()=>setFiles(prev=>prev.filter((_,j)=>j!==i))}
                className="absolute top-1 right-1 bg-white rounded-full p-0.5">
                <X className="h-4 w-4 text-red-500"/>
              </button>
              {isImage(f.name)
                ? <img src={URL.createObjectURL(f)} className="h-full w-full object-cover"/>
                : <div className="flex flex-col items-center justify-center h-full bg-gray-50 text-primary-600">
                    <FileText className="h-8 w-8"/><span className="text-[10px] mt-1">PDF</span>
                  </div>
              }
            </div>
          )}
          {/* add new */}
          <div {...getRootProps()} className="h-24 w-24 flex items-center justify-center border-2 border-dashed rounded cursor-pointer">
            <input {...getInputProps()}/>
            <Plus className="h-6 w-6 text-gray-500"/>
          </div>
        </div>
      </div>
    </form>
  )
}

// Модалка шаринга множества
function BulkShareModal({
  count,
  onCancel,
  onSend,
}: {
  count: number
  onCancel(): void
  onSend(email: string): Promise<void>
}) {
  const [email, setEmail] = useState('')
  const [err, setErr]     = useState<string|null>(null)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center">
      <div className="bg-white rounded p-6 w-80">
        <h2 className="mb-4">Share {count} records</h2>
        <input
          type="email"
          placeholder="Recipient email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="border rounded p-2 w-full mb-2"
        />
        {err && <p className="text-red-600 mb-2">{err}</p>}
        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={async () => {
            if (!email) { setErr('Введите email'); return }
            try {
              await onSend(email)
            } catch {
              setErr('Не удалось отправить')
            }
          }}>
            Send
          </Button>
        </div>
      </div>
    </div>
  )
}
