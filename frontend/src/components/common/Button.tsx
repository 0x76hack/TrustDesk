import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'destructive' | 'success' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-bold rounded-xl transition-all duration-150 focus:outline-hidden focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed select-none cursor-pointer';

  const sizeStyles = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  }[size];

  const variantStyles = {
    primary:
      'bg-[#FC8019] hover:bg-[#E26A00] active:bg-[#D45D00] text-white shadow-xs focus:ring-[#FC8019]',
    secondary:
      'bg-white hover:bg-[#FFF2E5] hover:text-[#FC8019] active:bg-[#FFE8D6] text-[#282C3F] border border-[#D4D5D9] shadow-2xs focus:ring-[#FC8019]',
    outline:
      'bg-transparent hover:bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019] focus:ring-[#FC8019]',
    destructive:
      'bg-[#EC3D25] hover:bg-[#D32F2F] active:bg-[#B71C1C] text-white shadow-xs focus:ring-[#EC3D25]',
    success:
      'bg-[#60B246] hover:bg-[#4E9B36] active:bg-[#3D8527] text-white shadow-xs focus:ring-[#60B246]',
    ghost:
      'bg-transparent hover:bg-[#F4F5F8] text-[#686B78] active:bg-[#E9E9EB] focus:ring-[#D4D5D9]',
  }[variant];

  return (
    <button
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="font-mono text-xs font-bold animate-pulse mr-1.5">[...]</span>
      ) : (
        leftIcon
      )}
      <span>{children}</span>
      {!isLoading && rightIcon}
    </button>
  );
};
