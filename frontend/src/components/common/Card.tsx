import React from 'react';
import { twMerge } from 'tailwind-merge';

interface CardProps {
  title?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  title,
  icon,
  children,
  footer,
  className,
  onClick,
  hoverable = false,
}) => {
  return (
    <div
      className={twMerge(
        'bg-white rounded-lg shadow overflow-hidden transition-all duration-200',
        hoverable && 'hover:shadow-md hover:translate-y-[-2px] cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {(title || icon) && (
        <div className="px-6 py-4 border-b border-gray-200 flex items-center">
          {icon && <span className="mr-3 text-primary-600">{icon}</span>}
          {title && <h3 className="text-lg font-medium text-gray-900">{title}</h3>}
        </div>
      )}
      <div className="px-6 py-4">{children}</div>
      {footer && (
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-200">
          {footer}
        </div>
      )}
    </div>
  );
};
