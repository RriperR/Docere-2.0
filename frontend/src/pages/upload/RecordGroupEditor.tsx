import React from 'react'
import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'
import { Button } from '../../components/common/Button'
import { DateInput } from '../../components/common/DateInput'
import { formatDateForDisplay } from '../../utils/dates'
import { warningAffectsFile } from '../../utils/importWarnings'
import type { AiFieldName, AiRun, AppliedAi } from '../../api/importAi'
import type { ImportPatientDraft } from '../../stores/uploadStore'
import AiSuggestions from './AiSuggestions'
import { formatFileSize, getRelevantDuplicateCandidates, recordTypeLabels, type GroupDecisionState, type PatientDecisionState, type ReviewDocument } from './reviewState'

/** Редактор только выбранной записи; черновики остальных документов хранятся выше. */
export default function RecordGroupEditor({ group, sourceGroup, decision, patientCandidates, warnings, serverDuplicate,
  status, regrouping, aiRun, onChange, onMove, onSource, onApplyAi }: {
  group: GroupDecisionState
  sourceGroup: ImportPatientDraft['record_groups'][number] | undefined
  decision: PatientDecisionState
  patientCandidates: ImportPatientDraft[]
  warnings: string[]
  serverDuplicate: boolean
  status: ReviewDocument['status'] | undefined
  regrouping: boolean
  aiRun: AiRun | null | undefined
  onChange: (patch: Partial<GroupDecisionState>) => void
  onMove: (targetId: string | null) => Promise<void>
  onSource: (fileId: string, page: number) => void
  onApplyAi: (name: AiFieldName, value: string, reference: AppliedAi, emptyOnly?: boolean) => void
}) {
  const needsDate = decision.action !== 'skip' && group.action === 'create' && !group.event_date
  const duplicateCandidates = getRelevantDuplicateCandidates(sourceGroup, decision)
  const hasDuplicates = duplicateCandidates.length > 0 || serverDuplicate
  return (
    <div
      key={group.group_id}
      id={`review-group-${group.group_id}`}
      className="scroll-mt-28 rounded-lg border border-gray-100 p-4"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <FileText className="h-4 w-4 text-primary-600" />
          <p className="min-w-0 break-words font-medium text-gray-900">{group.title || sourceGroup?.title || 'Запись'}</p>
          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${status === 'skipped' ? 'border-gray-200 bg-gray-50 text-gray-600' : status === 'needs_data' ? 'border-warning-200 bg-warning-50 text-warning-700' : 'border-success-200 bg-success-50 text-success-700'}`}>
            {decision.action === 'skip' || group.action === 'skip' ? 'Пропущен' : status === 'needs_data' ? 'Нужны данные' : 'Можно сохранить'}
          </span>
          {hasDuplicates && (
            <span className="rounded-full border border-warning-200 bg-warning-50 px-2 py-0.5 text-xs font-medium text-warning-700">
              {group.allow_possible_duplicate ? 'Дубль подтверждён' : 'Возможный дубль'}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={group.action === 'create'}
              disabled={decision.action === 'skip'}
              onChange={(event) => onChange({ action: event.target.checked ? 'create' : 'skip' })}
            />
            Сохранить запись в историю
          </label>
        </div>
      </div>

      {hasDuplicates && (
        <div className="mb-3 rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
          <p className="font-medium">Похожие записи уже есть у пациента</p>
          {serverDuplicate && <p className="mt-2">Сервер обнаружил дубль при окончательной проверке. Сравните запись с историей перед подтверждением.</p>}
          {serverDuplicate && decision.patient_passport_id && <Link className="font-medium underline" to={`/patients/${decision.patient_passport_id}`} target="_blank" rel="noopener noreferrer">Проверить историю пациента в новой вкладке</Link>}
          <div className="mt-2 space-y-1">
            {duplicateCandidates.map((candidate) => (
              <div key={candidate.record_id} className="flex flex-wrap items-center gap-2 text-xs">
                <span>{candidate.title || 'Медицинская запись'}</span>
                <span>{recordTypeLabels[candidate.record_type] ?? candidate.record_type}</span>
                <span>{formatDateForDisplay(candidate.event_date)}</span>
                <span className="text-warning-700">
                  совпадают дата и название
                </span>
                <Link
                  to={`/patients/${candidate.patient_passport_id}`}
                  className="font-medium text-primary-700 hover:underline"
                >
                  Открыть карточку
                </Link>
              </div>
            ))}
          </div>
          {group.action === 'create' && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant={group.allow_possible_duplicate ? 'outline' : 'primary'}
                onClick={() => onChange({ allow_possible_duplicate: !group.allow_possible_duplicate })}
              >
                {group.allow_possible_duplicate ? 'Отменить подтверждение' : 'Импортировать всё равно'}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onChange({ action: 'skip' })}
              >
                Пропустить запись
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 2xl:grid-cols-2">
        <label className="min-w-0 space-y-1">
          <span className="text-xs font-medium text-gray-500">Тип</span>
          <select
            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
            value={group.record_type ?? 'other'}
            disabled={decision.action === 'skip' || group.action === 'skip'}
            onChange={(event) => onChange({ record_type: event.target.value })}
          >
            {Object.entries(recordTypeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 space-y-1">
          <span className="text-xs font-medium text-gray-500">Дата события</span>
          <DateInput
            className={`w-full rounded-md border px-3 py-2 text-sm ${
              needsDate ? 'border-warning-300 bg-warning-50' : 'border-gray-200'
            }`}
            value={group.event_date ?? ''}
            disabled={decision.action === 'skip' || group.action === 'skip'}
            onChange={(value) => onChange({ event_date: value })}
          />
          {sourceGroup && sourceGroup.event_date_candidates.length > 1 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {sourceGroup.event_date_candidates.map((candidate) => {
                const selected = group.event_date === candidate
                return (
                  <button
                    type="button"
                    key={`${group.group_id}-${candidate}`}
                    disabled={decision.action === 'skip' || group.action === 'skip'}
                    className={[
                      'rounded-sm border px-2 py-1 text-xs transition-colors',
                      selected
                        ? 'border-primary-500 bg-primary-50 text-primary-700'
                        : 'border-gray-200 bg-white text-gray-600 hover:border-primary-300',
                    ].join(' ')}
                    onClick={() => onChange({ event_date: candidate })}
                  >
                    {formatDateForDisplay(candidate)}
                  </button>
                )
              })}
            </div>
          )}
        </label>
        <label className="min-w-0 space-y-1">
          <span className="text-xs font-medium text-gray-500">Название</span>
          <input
            className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
            value={group.title ?? ''}
            disabled={decision.action === 'skip' || group.action === 'skip'}
            onChange={(event) => onChange({ title: event.target.value })}
          />
        </label>
      </div>

      <label className="mt-3 block text-sm">Пациент этого документа<select className="mt-1 w-full rounded-md border border-gray-200 p-2" value={decision.candidate_id} disabled={regrouping} onChange={e => void onMove(e.target.value === '__new' ? null : e.target.value)}><option value={decision.candidate_id}>Текущий пациент</option>{patientCandidates.filter(p => p.candidate_id !== decision.candidate_id).map(p => <option key={p.candidate_id} value={p.candidate_id}>{p.fio ?? 'Другой кандидат пациента'}</option>)}<option value="__new">Отдельный пациент</option></select></label>
      <label className="mt-3 block text-sm">Клиническое описание<textarea className="mt-1 w-full rounded-md border border-gray-200 p-3" maxLength={10000} value={group.clinical_summary ?? ''} onChange={e => onChange({ clinical_summary: e.target.value })} /></label>
      {aiRun && sourceGroup?.files.map(file => {
        const document = aiRun?.documents.find(d => d.file_id === file.id)
        if (!document) return null
        const needsIdentity = document.result.patient_conflict || document.result.fields?.fio || document.result.fields?.date_of_birth
        return <React.Fragment key={file.id}><AiSuggestions document={document} runId={aiRun!.id} currentValues={{ fio: decision.fio, date_of_birth: decision.date_of_birth, title: group.title, event_date: group.event_date, record_type: group.record_type, clinical_summary: group.clinical_summary }} canApplyIdentity={decision.action === 'create'} onSource={onSource} onApply={(name, value, reference, emptyOnly) => onApplyAi(name, value, reference, emptyOnly)} />
          {needsIdentity && !document.result.multiple_patients && <label className="mt-2 flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm"><input type="checkbox" checked={group.patient_identity_confirmed ?? false} onChange={e => onChange({ patient_identity_confirmed: e.target.checked })} />Я проверил, что документ относится к выбранному пациенту</label>}</React.Fragment>
      })}
      {sourceGroup && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-gray-500">
            Файлов: {sourceGroup.files.length}; DICOM: {sourceGroup.files.filter((file) => file.is_dicom).length}
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            {sourceGroup.files.map((file) => {
              const hasWarning = warningAffectsFile(warnings, file.path, file.filename)
              return (
                <div key={file.path} className="rounded-sm border border-gray-100 bg-gray-50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 break-all font-medium text-gray-800">{file.filename}</span>
                    <span className="shrink-0 text-gray-500">{formatFileSize(file.size_bytes)}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-gray-500">
                    <span>{file.is_dicom ? 'DICOM' : file.mime_type}</span>
                    {hasWarning && <span className="text-warning-700">Требует проверки</span>}
                  </div>
                  {file.id && <button type="button" aria-label={`Открыть документ ${file.filename}`} className="mt-2 font-medium text-primary-700 underline" onClick={() => onSource(file.id!, 1)}>Открыть документ</button>}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
