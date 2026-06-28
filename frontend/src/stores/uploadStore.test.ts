import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from '../api/api'
import { type UploadJob, useUploadStore } from './uploadStore'

vi.mock('../api/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

const job: UploadJob = {
  id: 'job-1',
  status: 'needs_review',
  original_filename: 'demo.zip',
  archive_storage_key: 'imports/demo.zip',
  size_bytes: 1024,
  report_json: { message: 'Review required', patients: [] },
  review_decisions: [],
  review_updated_at: null,
  created_at: '2026-06-28T10:00:00Z',
  finished_at: null,
}

describe('upload store', () => {
  beforeEach(() => {
    useUploadStore.getState().clearUpload()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.put).mockReset()
  })

  it('loads import jobs and finishes the loading state', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [job] })

    await useUploadStore.getState().listJobs()

    expect(useUploadStore.getState()).toMatchObject({ jobs: [job], isLoadingJobs: false, error: null })
  })

  it('keeps a clinician-facing error when resolve requires duplicate confirmation', async () => {
    vi.mocked(api.post).mockRejectedValue({
      response: { data: { detail: { code: 'duplicate_confirmation_required' } } },
    })

    await expect(useUploadStore.getState().resolveJob(job.id, [])).rejects.toBeDefined()

    expect(useUploadStore.getState().error).toContain('похожая запись')
    expect(useUploadStore.getState().isResolving).toBe(false)
  })

  it('stores review draft metadata after autosave', async () => {
    useUploadStore.setState({ currentJob: job })
    vi.mocked(api.put).mockResolvedValue({
      data: { decisions: [], updated_at: '2026-06-28T10:05:00Z' },
    })

    const updatedAt = await useUploadStore.getState().saveReviewDraft(job.id, [])

    expect(updatedAt).toBe('2026-06-28T10:05:00Z')
    expect(useUploadStore.getState().currentJob?.review_updated_at).toBe(updatedAt)
    expect(useUploadStore.getState().isSavingReviewDraft).toBe(false)
  })
})
