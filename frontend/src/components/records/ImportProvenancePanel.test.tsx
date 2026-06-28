import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ImportProvenancePanel } from './ImportProvenancePanel'

describe('ImportProvenancePanel', () => {
  it('renders archive provenance for an imported record', () => {
    render(
      <ImportProvenancePanel
        payloadJson={{
          import_provenance: {
            source_archive: 'demo.zip',
            import_job_id: 'job-1',
            files: [{ path: 'study.dcm' }, { path: 'report.pdf' }],
          },
        }}
      />,
    )

    expect(screen.getByText('demo.zip')).toBeInTheDocument()
    expect(screen.getByText('job-1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('stays hidden for records without import provenance', () => {
    const { container } = render(<ImportProvenancePanel payloadJson={{}} />)

    expect(container).toBeEmptyDOMElement()
  })
})
