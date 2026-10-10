import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import api from '../../api/api'
import CaseDocumentPanel from './CaseDocumentPanel'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('retrieves protected blobs and destroys the document URL when the workspace is removed', async () => {
  const create = vi.fn(() => 'blob:protected-document')
  const revoke = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', { value: create, configurable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: revoke, configurable: true })
  const get = vi.spyOn(api, 'get').mockImplementation(async url => {
    if (String(url).endsWith('/attachments/file-1')) return { data: new Blob(['%PDF-1.4']), headers: { 'content-type': 'application/pdf' } }
    return { data: { id: 'record-1', title: 'Synthetic record', event_date: '2026-01-01', clinical_summary: '',
      attachments: [{ id: 'file-1', filename: 'scan.pdf', mime_type: 'application/pdf', size_bytes: 42 }], comments: [] } }
  })
  const view = render(<CaseDocumentPanel caseId="case-1" recordId="record-1" attachmentId="file-1"
    onClose={vi.fn()} onAccessLost={vi.fn()} onReference={vi.fn()} />)
  await waitFor(() => expect(screen.getByTitle('Просмотр PDF')).toHaveAttribute('src', 'blob:protected-document'))
  expect(get.mock.calls.some(([url]) => url === '/cases/case-1/materials/record-1/attachments/file-1')).toBe(true)
  view.unmount()
  expect(revoke).toHaveBeenCalledWith('blob:protected-document')
})

it('does not display an attachment response that arrives after selecting another record', async () => {
  let resolveFirst!: (result: unknown) => void
  Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(() => 'blob:current'), configurable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true })
  vi.spyOn(api, 'get').mockImplementation(async url => {
    if (String(url).endsWith('/attachments/first')) return new Promise(resolve => { resolveFirst = resolve })
    if (String(url).endsWith('/attachments/second')) return { data: new Blob(['new']), headers: { 'content-type': 'image/png' } }
    const second = String(url).endsWith('/record-2')
    return { data: { id: second ? 'record-2' : 'record-1', title: 'Record', event_date: '2026-01-01', clinical_summary: '',
      attachments: [{ id: second ? 'second' : 'first', filename: 'scan.png', mime_type: 'image/png', size_bytes: 42 }], comments: [] } }
  })
  const props = { caseId: 'case-1', onClose: vi.fn(), onAccessLost: vi.fn(), onReference: vi.fn() }
  const view = render(<CaseDocumentPanel {...props} recordId="record-1" attachmentId="first" />)
  await waitFor(() => expect(resolveFirst).toBeDefined())
  view.rerender(<CaseDocumentPanel {...props} recordId="record-2" attachmentId="second" />)
  await waitFor(() => expect(screen.getByAltText('Вложение медицинской записи')).toHaveAttribute('src', 'blob:current'))
  resolveFirst({ data: new Blob(['old']), headers: { 'content-type': 'application/pdf' } })
  await waitFor(() => expect(screen.queryByTitle('Просмотр PDF')).not.toBeInTheDocument())
})

it('rejects a record from a different patient before loading any file', async () => {
  const { default: DocumentViewer } = await import('../../components/records/DocumentViewer')
  const lost = vi.fn(async () => undefined)
  const get = vi.spyOn(api, 'get').mockResolvedValue({ data: { id: 'record-1', patient_passport_id: 'other-patient',
    title: 'Other patient record', event_date: '2026-01-01', clinical_summary: 'Private text',
    attachments: [{ id: 'file-1', filename: 'scan.pdf', mime_type: 'application/pdf', size_bytes: 42 }], comments: [] } })
  render(<DocumentViewer patientId="patient-1" recordId="record-1" attachmentId="file-1" onClose={vi.fn()} onAccessLost={lost} />)
  await waitFor(() => expect(lost).toHaveBeenCalled())
  expect(get).toHaveBeenCalledTimes(1)
  expect(get.mock.calls[0][0]).toBe('/records/record-1')
  expect(screen.queryByText('Private text')).not.toBeInTheDocument()
})
