import { Component, type ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button } from './Button'

/** Даёт путь восстановления при ошибке страницы, в том числе после обновления сборки. */
export class PageErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return <main className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <section role="alert" className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-card">
        <p className="text-sm font-semibold text-primary-700">Docere</p>
        <h1 className="mt-3 text-2xl font-bold text-gray-900">Не удалось открыть страницу</h1>
        <p className="mt-3 text-sm leading-relaxed text-gray-600">Возможно, приложение обновилось или прервалось соединение. Обновите страницу, чтобы продолжить.</p>
        <p className="mt-2 text-sm text-gray-500">Несохранённый текст может быть потерян.</p>
        <Button className="mt-6" icon={<RefreshCw size={16} aria-hidden="true" />} onClick={() => window.location.reload()}>Обновить страницу</Button>
      </section>
    </main>
  }
}
