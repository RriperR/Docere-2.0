import React, { useState, useCallback } from 'react'
import { usePatientsStore } from '../stores/patientsStore'
import { useDropzone } from 'react-dropzone'
import { Button } from './common/Button'

interface Props {
  patientId: string
  onClose: () => void
}

export const AddRecordModal: React.FC<Props> = ({ patientId, onClose }) => {
  const createPatientRecord = usePatientsStore(s => s.createPatientRecord)
  const [notes, setNotes] = useState('')
  const [visitDate, setVisitDate] = useState('')
  const [location, setLocation] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string|null>(null)

  const onDrop = useCallback((accepted: File[]) => {
    setFiles(f => [...f, ...accepted])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: { 'image/*': [], 'application/pdf': [] }
  })

  const hasAtLeastOne = notes || visitDate || location || files.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!hasAtLeastOne) {
      setError('Заполните хотя бы одно поле или добавьте файл')
      return
    }
    setLoading(true)
    setError(null)
    // собираем FormData
    const form = new FormData()
    if (notes)     form.append('notes', notes)
    if (visitDate) form.append('visit_date', visitDate)
    if (location)  form.append('appointment_location', location)
    files.forEach(f => form.append('files', f))  // на бэке смотреть request.FILES.getlist('files')
    await createPatientRecord(patientId, form)
    setLoading(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-6 rounded-lg w-full max-w-lg space-y-4"
      >
        <h2 className="text-xl font-semibold">Новая запись</h2>

        {error && <p className="text-red-600">{error}</p>}

        <label className="block">
          Дата визита
          <input
            type="date"
            value={visitDate}
            onChange={e => setVisitDate(e.target.value)}
            className="mt-1 w-full border rounded p-2"
          />
        </label>

        <label className="block">
          Место приёма
          <input
            type="text"
            value={location}
            onChange={e => setLocation(e.target.value)}
            placeholder="Где был приём"
            className="mt-1 w-full border rounded p-2"
          />
        </label>

        <label className="block">
          Комментарий / Заключение
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={4}
            className="mt-1 w-full border rounded p-2"
          />
        </label>

        <div
          {...getRootProps()}
          className={`mt-2 p-4 border-2 border-dashed rounded text-center cursor-pointer
            ${isDragActive ? 'border-primary-600 bg-primary-50' : 'border-gray-300'}`}
        >
          <input {...getInputProps()} />
          {isDragActive
            ? <p>Отпустите файлы, чтобы добавить</p>
            : <p>Перетащите сюда файлы или кликните, чтобы выбрать ({files.length} добавлено)</p>
          }
        </div>

        {files.length > 0 && (
          <ul className="mt-2 max-h-32 overflow-auto text-sm">
            {files.map((f, i) => (
              <li key={i} className="flex justify-between">
                <span>{f.name}</span>
                <button
                  type="button"
                  onClick={() => setFiles(fs => fs.filter((_, idx) => idx !== i))}
                  className="text-red-500"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex justify-end space-x-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border rounded"
            disabled={loading}
          >
            Отмена
          </button>
          <Button type="submit" disabled={loading}>
            {loading ? 'Сохраняю…' : 'Сохранить'}
          </Button>
        </div>
      </form>
    </div>
  )
}
