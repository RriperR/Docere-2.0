import React, { forwardRef } from 'react';
import DatePicker, { registerLocale } from 'react-datepicker';
import { ru } from 'date-fns/locale/ru';
import { twMerge } from 'tailwind-merge';

import 'react-datepicker/dist/react-datepicker.css';

registerLocale('ru', ru);

interface DateInputProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    'type' | 'value' | 'onChange' | 'onSelect'
  > {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  fullWidth?: boolean;
  value?: string | null;
  onChange: (value: string | null) => void;
}

const isoToDate = (value?: string | null): Date | null => {
  if (!value) return null;

  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;

  const [, yearRaw, monthRaw, dayRaw] = match;
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  const date = new Date(year, month - 1, day);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }

  return date;
};

const dateToIso = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const DateInput = forwardRef<HTMLInputElement, DateInputProps>(
  (
    {
      label,
      error,
      icon,
      className,
      fullWidth = true,
      value,
      disabled,
      onChange,
      placeholder = 'дд.мм.гггг',
      ...props
    },
    ref,
  ) => {
    const selectedDate = isoToDate(value);

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
            <div className="pointer-events-none absolute inset-y-0 left-0 z-10 flex items-center pl-3">
              <span className="text-gray-400">{icon}</span>
            </div>
          )}
          <DatePicker
            selected={selectedDate}
            onChange={(date) => onChange(date ? dateToIso(date) : null)}
            dateFormat="dd.MM.yyyy"
            locale="ru"
            strictParsing
            placeholderText={placeholder}
            disabled={disabled}
            isClearable={!props.required && !disabled}
            showPopperArrow={false}
            showMonthDropdown
            showYearDropdown
            dropdownMode="select"
            autoComplete="off"
            className={twMerge(
              'block rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm placeholder-gray-400 transition-colors focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200',
              icon ? 'pl-9' : 'pl-4',
              error
                ? 'border-error-300 bg-error-50 focus:border-error-400 focus:ring-error-200'
                : '',
              fullWidth && 'w-full',
              disabled && 'cursor-not-allowed opacity-60',
              className,
            )}
            calendarStartDay={1}
            popperClassName="docere-date-picker"
            wrapperClassName={fullWidth ? 'w-full' : undefined}
            customInputRef={ref as React.Ref<HTMLInputElement>}
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

DateInput.displayName = 'DateInput';
