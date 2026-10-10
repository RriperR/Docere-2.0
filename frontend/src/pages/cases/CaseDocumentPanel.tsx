import DocumentViewer, { type MaterialReference } from '../../components/records/DocumentViewer'
export type { MaterialReference } from '../../components/records/DocumentViewer'
export default function CaseDocumentPanel(props: {
  caseId: string; recordId: string; attachmentId: string | null; onClose: () => void
  onAccessLost: () => Promise<void>; onReference: (reference: MaterialReference) => void
}) { return <DocumentViewer {...props} /> }
