import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Card from './Card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText('Card content')).toBeInTheDocument()
  })

  it('applies selected styles when selected is true', () => {
    render(<Card selected>Selected card</Card>)
    const card = screen.getByText('Selected card')
    expect(card.className).toContain('border-emerald-500')
  })

  it('does not apply selected styles by default', () => {
    render(<Card>Default card</Card>)
    const card = screen.getByText('Default card')
    expect(card.className).not.toContain('border-emerald-500')
  })

  it('renders with custom className', () => {
    render(<Card className="custom-class">Content</Card>)
    const card = screen.getByText('Content')
    expect(card.className).toContain('custom-class')
  })
})
