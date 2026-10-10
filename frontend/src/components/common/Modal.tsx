import { useEffect, useRef, type ReactNode } from 'react'

export default function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const origin = document.activeElement as HTMLElement | null
    const dialog = panel.current
    dialog?.focus()
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close.current() }
      if (event.key !== 'Tab') return
      const controls = Array.from(dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]') ?? []).filter(element => element.getClientRects().length > 0)
      const first = controls[0], last = controls[controls.length - 1]
      if (!first) { event.preventDefault(); dialog?.focus(); return }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) { event.preventDefault(); first.focus() }
    }
    dialog?.addEventListener('keydown', handle)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { dialog?.removeEventListener('keydown', handle); document.body.style.overflow = previousOverflow; if (origin?.isConnected) origin.focus() }
  }, [])
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 p-3 sm:p-6">
    <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className="max-h-[95vh] w-full max-w-6xl overflow-auto rounded-2xl bg-white p-3 shadow-xl">
      {children}
    </div>
  </div>
}
