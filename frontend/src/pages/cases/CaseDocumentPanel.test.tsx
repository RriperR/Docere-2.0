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
