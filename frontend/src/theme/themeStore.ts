import { create } from 'zustand'

export type ThemePreference = 'light' | 'dark' | 'system'
export const THEME_STORAGE_KEY = 'docere.theme'
const SYSTEM_THEME_QUERY = '(prefers-color-scheme: dark)'

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system'
}

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemePreference(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

/** Меняет только оформление приложения: оригиналы документов сохраняют свои цвета. */
function applyTheme(preference: ThemePreference): void {
  const systemDark = window.matchMedia?.(SYSTEM_THEME_QUERY).matches ?? false
  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
}

interface ThemeState {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
}

export const useThemeStore = create<ThemeState>((set) => ({
  preference: readPreference(),
  setPreference: (preference) => {
    try { localStorage.setItem(THEME_STORAGE_KEY, preference) } catch { /* Выбор работает и без хранилища. */ }
    applyTheme(preference)
    set({ preference })
  },
}))

/** Следит за темой ОС и выбором в соседних вкладках; возвращает очистку подписок. */
export function subscribeToThemeChanges(): () => void {
  const media = window.matchMedia?.(SYSTEM_THEME_QUERY)
  const onSystemChange = () => applyTheme(useThemeStore.getState().preference)
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) return
    const preference = readPreference()
    useThemeStore.setState({ preference })
    applyTheme(preference)
  }
  applyTheme(useThemeStore.getState().preference)
  media?.addEventListener('change', onSystemChange)
  window.addEventListener('storage', onStorage)
  return () => {
    media?.removeEventListener('change', onSystemChange)
    window.removeEventListener('storage', onStorage)
  }
}
