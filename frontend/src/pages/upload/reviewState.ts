import { Patient } from '../../stores/patientsStore'
import { ImportPatientDecision, ImportPatientDraft, ImportRecordGroupDecision } from '../../stores/uploadStore'
import { formatDateForDisplay } from '../../utils/dates'

export type PatientAction = 'existing' | 'create' | 'skip'

export type GroupDecisionState = ImportRecordGroupDecision & {
  action: 'create' | 'skip'
}

export type PatientDecisionState = {
  candidate_id: string
  action: PatientAction
  patient_passport_id: string
  fio: string
  date_of_birth: string
  record_groups: GroupDecisionState[]
}

export type PatientOption = {
  id: string
  label: string
  priority: number
}

export type BulkPatchState = {
  record_type: string
  event_date: string
}

export const recordTypeLabels: Record<string, string> = {
  exam_result: 'Обследование',
  lab_result: 'Анализ',
  consultation_result: 'Консультация',
  other: 'Другое',
}

export function buildPatientOptions(accessiblePatients: Patient[], patientCandidate: ImportPatientDraft): PatientOption[] {
  const matchTypeById = new Map(patientCandidate.existing_matches.map((match) => [match.id, match.match_type]))
  return accessiblePatients
    .map((patient) => {
      const matchType = matchTypeById.get(patient.id)
      const matchLabel = matchType === 'exact' ? 'точное совпадение' : matchType === 'fuzzy' ? 'похожая карточка' : ''
      return {
        id: patient.id,
        priority: matchType === 'exact' ? 0 : matchType === 'fuzzy' ? 1 : 2,
        label: [
          patient.fio,
          patient.birthday ? formatDateForDisplay(patient.birthday) : '',
          matchLabel,
        ].filter(Boolean).join(', '),
      }
    })
    .sort((left, right) => left.priority - right.priority || left.label.localeCompare(right.label))
}

export function toInitialDecision(patient: ImportPatientDraft): PatientDecisionState {
  return {
    candidate_id: patient.candidate_id,
    action: 'create',
    patient_passport_id: '',
    fio: patient.fio ?? '',
    date_of_birth: patient.date_of_birth ?? '',
    record_groups: patient.record_groups.map((group) => ({
      group_id: group.group_id,
      action: 'create',
      record_type: group.record_type,
      event_date: group.event_date,
      title: group.title,
      clinical_summary: '',
      allow_possible_duplicate: false,
    })),
  }
}

export function restoreDecisions(
  patients: ImportPatientDraft[],
  savedDecisions: ImportPatientDecision[],
): PatientDecisionState[] {
  const savedByCandidate = new Map(savedDecisions.map((decision) => [decision.candidate_id, decision]))
  return patients.map((patient) => {
    const initial = toInitialDecision(patient)
    const saved = savedByCandidate.get(patient.candidate_id)
    if (!saved) return initial
    const savedGroups = new Map(saved.record_groups.map((group) => [group.group_id, group]))
    return {
      ...initial,
      action: saved.action,
      patient_passport_id: saved.patient_passport_id ?? '',
      fio: saved.fio ?? initial.fio,
      date_of_birth: saved.date_of_birth ?? '',
      record_groups: initial.record_groups.map((group) => {
        const savedGroup = savedGroups.get(group.group_id)
        return savedGroup
          ? {
              ...group,
              ...savedGroup,
              event_date: savedGroup.event_date ?? null,
              allow_possible_duplicate: savedGroup.allow_possible_duplicate ?? false,
            }
          : group
      }),
    }
  })
}

export function validateDecisions(decisions: PatientDecisionState[], patients: ImportPatientDraft[]): string {
  for (const decision of decisions) {
    if (decision.action === 'skip') continue
    if (decision.action === 'existing' && !decision.patient_passport_id) {
      return 'Выберите существующую карточку пациента или создайте новую.'
    }
    if (decision.action === 'create' && !decision.fio.trim()) {
      return 'Укажите ФИО для новой карточки пациента.'
    }
    for (const group of decision.record_groups) {
      const patient = patients.find((item) => item.candidate_id === decision.candidate_id)
      const sourceGroup = patient?.record_groups.find((item) => item.group_id === group.group_id)
      if (group.action === 'create' && !group.event_date) {
        return 'Укажите дату события для каждой импортируемой медицинской записи.'
      }
      if (
        group.action === 'create' &&
        getRelevantDuplicateCandidates(sourceGroup, decision).length > 0 &&
        !group.allow_possible_duplicate
      ) {
        return 'Для возможного дубля выберите «Импортировать всё равно» или пропустите запись.'
      }
    }
  }
  return ''
}

export function toPayload(decision: PatientDecisionState): ImportPatientDecision {
  return {
    candidate_id: decision.candidate_id,
    action: decision.action,
    patient_passport_id: decision.action === 'existing' ? decision.patient_passport_id : undefined,
    fio: decision.action === 'create' ? decision.fio.trim() : undefined,
    date_of_birth: decision.action === 'create' ? decision.date_of_birth || null : undefined,
    record_groups: decision.record_groups.map((group) => ({
      group_id: group.group_id,
      action: group.action,
      record_type: group.record_type,
      event_date: group.event_date || null,
      title: group.title,
      clinical_summary: group.clinical_summary,
      patient_identity_confirmed: group.patient_identity_confirmed,
      applied_ai: group.applied_ai,
      allow_possible_duplicate: group.allow_possible_duplicate ?? false,
    })),
  }
}

export function getRelevantDuplicateCandidates(
  sourceGroup: ImportPatientDraft['record_groups'][number] | undefined,
  decision: PatientDecisionState,
) {
  if (!sourceGroup || decision.action !== 'existing' || !decision.patient_passport_id) return []
  return sourceGroup.duplicate_candidates.filter(
    (candidate) => candidate.patient_passport_id === decision.patient_passport_id,
  )
}

export function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 Б'
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export interface ReviewDocument {
  groupId: string
  candidateId: string
  filename: string
  patientName: string
  status: 'ready' | 'needs_data' | 'skipped'
  issue: string | null
}

/** Сводка относится к решениям врача, а не к подтверждению медицинской записи. */
export function buildReviewDocuments(
  patients: ImportPatientDraft[],
  decisions: PatientDecisionState[],
  serverDuplicates: string[],
  aiDocuments: import('../../api/importAi').AiDocument[] = [],
): ReviewDocument[] {
  return patients.flatMap(patient => patient.record_groups.map(source => {
    const decision = decisions.find(item => item.candidate_id === patient.candidate_id)
    const group = decision?.record_groups.find(item => item.group_id === source.group_id)
    const skipped = decision?.action === 'skip' || group?.action === 'skip'
    const documents = aiDocuments.filter(document => source.files.some(file => file.id === document.file_id))
    let issue: string | null = null
    if (!decision || !group) issue = 'Решения загружаются'
    else if (decision.action === 'existing' && !decision.patient_passport_id) issue = 'Выберите карточку пациента'
    else if (decision.action === 'create' && !decision.fio.trim()) issue = 'Укажите ФИО пациента'
    else if (!group.event_date) issue = 'Укажите дату события'
    else if ((getRelevantDuplicateCandidates(source, decision).length > 0 || serverDuplicates.includes(group.group_id)) && !group.allow_possible_duplicate) issue = 'Сравните возможный дубль'
    else if (documents.some(document => document.result.multiple_patients)) issue = 'В документе несколько пациентов — пропустите его'
    else if (documents.some(document => document.result.patient_conflict || document.result.fields?.fio || document.result.fields?.date_of_birth) && !group.patient_identity_confirmed) issue = 'Подтвердите принадлежность пациенту'
    return {
      groupId: source.group_id, candidateId: patient.candidate_id,
      filename: source.files[0]?.filename ?? group?.title ?? source.title ?? 'Документ',
      patientName: decision?.action === 'existing' ? 'Выбранная карточка пациента' : decision?.fio || patient.fio || 'Пациент не указан',
      status: skipped ? 'skipped' : issue ? 'needs_data' : 'ready',
      issue: skipped ? null : issue,
    }
  }))
}
