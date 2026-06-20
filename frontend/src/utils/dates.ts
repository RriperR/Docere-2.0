export const formatDateForDisplay = (isoDate?: string | null): string => {
  if (!isoDate) return ''
  const [year, month, day] = isoDate.split('-')
  if (!year || !month || !day) return isoDate
  return `${day}/${month}/${year}`
}

export const normalizeDateInput = (value: string): string => {
  const digits = value.replace(/\D/g, '').slice(0, 8)
  if (digits.length <= 2) return digits
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
}

export const parseDisplayDateToIso = (value: string): string | null => {
  const match = value.trim().match(/^(\d{2})[/.](\d{2})[/.](\d{4})$/)
  if (!match) return null

  const [, dayRaw, monthRaw, yearRaw] = match
  const day = Number(dayRaw)
  const month = Number(monthRaw)
  const year = Number(yearRaw)
  const date = new Date(Date.UTC(year, month - 1, day))

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null
  }

  return `${yearRaw}-${monthRaw}-${dayRaw}`
}
