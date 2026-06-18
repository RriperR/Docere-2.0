import React, { forwardRef } from 'react';
import { twMerge } from 'tailwind-merge';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, className, fullWidth = true, ...props }, ref) => {
    return (
      <div className={`${fullWidth ? 'w-full' : ''} mb-0 last:mb-0`}>
        {label && (
          <label
            htmlFor={props.id}
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <span className="text-gray-400">{icon}</span>
            </div>
          )}
          <input
            ref={ref}
            className={twMerge(
              'block rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm placeholder-gray-400 transition-colors focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200',
              icon ? 'pl-9' : 'pl-4',
              error
                ? 'border-error-300 bg-error-50 focus:border-error-400 focus:ring-error-200'
                : '',
              fullWidth && 'w-full',
              props.disabled && 'cursor-not-allowed opacity-60',
              className,
            )}
            {...props}
          />
        </div>
        {error && (
          <p className="mt-1 text-xs font-medium text-error-600">{error}</p>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';
