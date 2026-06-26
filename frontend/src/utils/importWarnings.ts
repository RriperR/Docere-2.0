export type ImportWarningView = {
  label: string
  tone: string
  warning: string
}

export type ImportWarningGroup = {
  label: string
  tone: string
  warnings: string[]
}

export const warningView = (warning: string): ImportWarningView => {
  const text = warning.toLowerCase()
  if (text.includes('unsafe') || text.includes('system file')) {
    return { label: 'Безопасность', tone: 'border-error-200 bg-error-50 text-error-700', warning }
  }
  if (text.includes('empty file')) {
    return { label: 'Пустой файл', tone: 'border-gray-200 bg-gray-50 text-gray-700', warning }
  }
  if (text.includes('size limit') || text.includes('file count limit') || text.includes('compressed')) {
    return { label: 'Лимит архива', tone: 'border-warning-200 bg-warning-50 text-warning-700', warning }
  }
  if (text.includes('multiple date candidates')) {
    return { label: 'Выбор даты', tone: 'border-primary-200 bg-primary-50 text-primary-700', warning }
  }
  return { label: 'Внимание', tone: 'border-warning-200 bg-warning-50 text-warning-700', warning }
}

export const warningAffectsFile = (warnings: string[], path: string, filename: string): boolean =>
  warnings.some((warning) => warning.includes(path) || warning.includes(filename))

export const groupedWarnings = (warnings: string[]): ImportWarningGroup[] => {
  const groups = new Map<string, ImportWarningGroup>()
  warnings.forEach((warning) => {
    const view = warningView(warning)
    const existing = groups.get(view.label)
    if (existing) {
      existing.warnings.push(warning)
      return
    }
    groups.set(view.label, { label: view.label, tone: view.tone, warnings: [warning] })
  })
  return Array.from(groups.values())
}
