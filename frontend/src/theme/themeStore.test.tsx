import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeSelector } from '../components/common/ThemeSelector'
import { subscribeToThemeChanges, THEME_STORAGE_KEY, useThemeStore } from './themeStore'

let darkSystem = false
let media: MediaQueryList
let stop: (() => void) | undefined

beforeEach(() => {
  darkSystem = false
  media = Object.assign(new EventTarget(), {
    get matches() { return darkSystem },
    media: '(prefers-color-scheme: dark)',
  }) as MediaQueryList
  // Object.assign evaluates getters; define a live value for system-change tests.
  Object.defineProperty(media, 'matches', { get: () => darkSystem })
  vi.stubGlobal('matchMedia', vi.fn(() => media))
  useThemeStore.setState({ preference: 'system' })
  stop = subscribeToThemeChanges()
})
afterEach(() => { stop?.(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('theme preference', () => {
  it('switches through the labelled control and persists the choice', () => {
    render(<ThemeSelector />)
    fireEvent.change(screen.getByRole('combobox', { name: 'Тема' }), { target: { value: 'dark' } })
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('follows system changes only when system is selected and cleans up listeners', () => {
    darkSystem = true
    media.dispatchEvent(new Event('change'))
    expect(document.documentElement.dataset.theme).toBe('dark')
    useThemeStore.getState().setPreference('light')
    media.dispatchEvent(new Event('change'))
    expect(document.documentElement.dataset.theme).toBe('light')
    useThemeStore.getState().setPreference('system')
    expect(document.documentElement.dataset.theme).toBe('dark')
    stop?.()
    darkSystem = false
    media.dispatchEvent(new Event('change'))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('synchronizes other tabs and treats invalid or removed values as system', () => {
    render(<ThemeSelector />)
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY })))
    expect(screen.getByRole('combobox', { name: 'Тема' })).toHaveValue('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'invalid')
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY })))
    expect(screen.getByRole('combobox', { name: 'Тема' })).toHaveValue('system')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('still changes theme when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
    expect(() => useThemeStore.getState().setPreference('dark')).not.toThrow()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
