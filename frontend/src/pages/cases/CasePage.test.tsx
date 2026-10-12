import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { caseApi, type CaseView, type ClinicalCase } from '../../api/cases'
import CasePage from './CasePage'

vi.mock('../../api/caseUpdates', () => ({ watchChanges: vi.fn().mockResolvedValue(undefined) }))
vi.mock('./CaseMaterials', () => ({ default: ({ c, onOpen }: { c: ClinicalCase; onOpen: (id: string) => void }) =>
  <button onClick={() => onOpen(c.record_ids[0])}>Открыть документ</button> }))
vi.mock('./CaseAiSummary', () => ({ default: () => null }))
vi.mock('./CaseDiscussion', () => ({ default: () => null }))
vi.mock('./CaseConclusion', () => ({ default: () => null }))
vi.mock('./CaseDocumentPanel', () => ({ default: ({ recordId }: { recordId: string }) =>
  <aside role="dialog">{recordId}</aside> }))

afterEach(() => vi.restoreAllMocks())

function view(id: string): CaseView {
  return { id, status: 'active', membership_status: 'accepted', coordinator_id: 'doctor', coordinator_name: 'Doctor',
    management_members: [], unread_messages: 0, patient_name: `Patient ${id}`, material_count: 1, accessible: true, invitation_terms: '',
    case: { id, patient_id: `patient-${id}`, coordinator_id: 'doctor', title: `Case ${id}`, question: 'Question',
      status: 'active', version: 1, sequence: 1, record_ids: [`record-${id}`], members: [], created_at: '', previous_case_id: null, published_record_id: null } }
}

function Workspace() {
  const navigate = useNavigate()
  return <><button onClick={() => navigate('/cases/second')}>Другой случай</button><CasePage /></>
}

it('does not carry an open document into another patient case', async () => {
  vi.spyOn(caseApi, 'get').mockImplementation(async id => view(id))
  render(<MemoryRouter initialEntries={['/cases/first']}><Routes>
    <Route path="/cases/:id" element={<Workspace />} />
  </Routes></MemoryRouter>)
  await screen.findByText('Case first')
  fireEvent.click(screen.getByText('Открыть документ'))
  expect(screen.getByRole('dialog')).toHaveTextContent('record-first')
  fireEvent.click(screen.getByText('Другой случай'))
  await screen.findByText('Case second')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
