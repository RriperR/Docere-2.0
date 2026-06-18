import React from 'react'
import { twMerge } from 'tailwind-merge'

interface CardProps {
  title?: string
  icon?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  className?: string
  onClick?: () => void
  hoverable?: boolean
  accent?: 'primary' | 'success' | 'warning' | 'error' | 'none'
}

const accentClasses: Record<string, string> = {
  primary: 'border-l-4 border-l-primary-500',
  success: 'border-l-4 border-l-success-500',
  warning: 'border-l-4 border-l-warning-500',
  error: 'border-l-4 border-l-error-500',
  none: '',
}

export const Card: React.FC<CardProps> = ({
  title,
  icon,
  children,
  footer,
  className,
  onClick,
  hoverable = false,
  accent = 'none',
}) => {
  return (
    <div
      className={twMerge(
        'rounded-xl border border-gray-100 bg-white shadow-card overflow-hidden transition-all duration-200',
        hoverable && 'hover:shadow-card-hover hover:-translate-y-px cursor-pointer',
        accentClasses[accent],
        className,
      )}
      onClick={onClick}
    >
      {(title || icon) && (
        <div className="border-b border-gray-100 px-6 py-4 flex items-center gap-3">
          {icon && <span className="text-primary-600">{icon}</span>}
          {title && <h3 className="text-base font-semibold text-gray-900">{title}</h3>}
        </div>
      )}
      <div className="px-6 py-4">{children}</div>
      {footer && (
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
          {footer}
        </div>
      )}
    </div>
  )
}
