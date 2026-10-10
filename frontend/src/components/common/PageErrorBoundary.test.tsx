import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { PageErrorBoundary } from './PageErrorBoundary'

it('offers explicit recovery instead of a blank page when a lazy page fails', () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  function FailedPage(): never { throw new Error('Failed to fetch dynamically imported module') }
  try {
    render(<PageErrorBoundary><FailedPage /></PageErrorBoundary>)
    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось открыть страницу')
    expect(screen.getByRole('button', { name: 'Обновить страницу' })).toBeEnabled()
    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument()
  } finally { consoleError.mockRestore() }
})
