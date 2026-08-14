import { cva } from 'class-variance-authority';

export const buttonVariants = cva(
  'button-content relative inline-flex min-h-8 cursor-pointer items-center justify-start gap-1.5 overflow-hidden rounded-xl font-sans uppercase tracking-button shadow-raised transition-[scale,transform,background-color,box-shadow] duration-(--prope-motion-duration-button) ease-in-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus active:scale-(--prope-scale-press) disabled:pointer-events-none disabled:shadow-none motion-reduce:transform-none',
  {
    variants: {
      intent: {
        primary: 'bg-primary text-ink hover:bg-primary-hover',
        secondary: 'bg-secondary text-inverse hover:bg-secondary-hover',
        neutral: 'border border-border bg-surface text-ink hover:bg-subtle',
        success: 'bg-success-strong text-inverse hover:brightness-90',
        warning: 'bg-warning-strong text-inverse hover:brightness-90',
        info: 'bg-info-strong text-inverse hover:brightness-90',
        danger: 'bg-danger-strong text-inverse hover:brightness-90',
        ghost: 'bg-transparent text-navigation-icon tracking-normal shadow-none hover:bg-surface/55',
      },
      size: {
        default: '',
        small: 'min-h-8 rounded-control px-3 py-1.5 text-caption',
        icon: 'size-10 min-h-10 p-0',
        navigationIcon: 'size-8 min-h-8 justify-center rounded-navigation-control !p-0 [&>svg]:size-navigation-icon [&>svg]:shrink-0',
      },
    },
    defaultVariants: { intent: 'primary', size: 'default' },
  },
);
