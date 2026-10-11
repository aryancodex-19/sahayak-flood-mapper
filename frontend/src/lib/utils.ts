import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-IN').format(n)
}

export function formatPopulation(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`
}

export function formatScore(n: number): string {
  return n.toFixed(2)
}

export function latLngBounds(
  lat: number,
  lng: number,
  halfSpan = 0.12
): [[number, number], [number, number]] {
  return [
    [lat - halfSpan, lng - halfSpan],
    [lat + halfSpan, lng + halfSpan],
  ]
}

export function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n))
}