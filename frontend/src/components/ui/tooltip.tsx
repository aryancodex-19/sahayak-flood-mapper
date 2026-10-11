import * as React from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'

import { cn } from '@/lib/utils'

interface TooltipProps extends React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Root> {}

const TooltipProvider = TooltipPrimitive.Provider

const Tooltip = ({ ...props }: TooltipProps) => (
  <TooltipPrimitive.Root {...props} />
)
Tooltip.displayName = TooltipPrimitive.Root.displayName

const TooltipTrigger = TooltipPrimitive.Trigger

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 overflow-hidden rounded-lg border border-white/10 bg-card/95 px-3 py-1.5 text-xs text-foreground shadow-glass backdrop-blur-md',
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent }