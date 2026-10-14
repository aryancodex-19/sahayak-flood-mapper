import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground',
        outline: 'text-foreground',
        cyan: 'border-transparent bg-cyan-500/15 text-cyan-300 ring-1 ring-inset ring-cyan-400/30',
        red: 'border-transparent bg-red-500/15 text-red-300 ring-1 ring-inset ring-red-400/30',
        green: 'border-transparent bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-400/30',
        amber: 'border-transparent bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-400/30',
        muted: 'border-transparent bg-muted text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
  VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }