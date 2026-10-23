import { useId } from 'react'
import { isThemePreference, useThemeStore } from '../../theme/themeStore'

/** Локальная настройка оформления, не зависящая от медицинского аккаунта. */
export function ThemeSelector() {
  const id = useId()
  const preference = useThemeStore(state => state.preference)
  const setPreference = useThemeStore(state => state.setPreference)
  return <div className="space-y-1.5">
    <label htmlFor={id} className="block text-sm font-medium text-gray-700">Тема</label>
    <select id={id} value={preference} onChange={event => {
      if (isThemePreference(event.target.value)) setPreference(event.target.value)
    }} className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900">
      <option value="system">Как в системе</option>
      <option value="light">Светлая</option>
      <option value="dark">Тёмная</option>
    </select>
  </div>
}
