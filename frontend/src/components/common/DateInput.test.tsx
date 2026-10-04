import { createRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DateInput } from './DateInput'

describe('DateInput', () => {
  it('forwards the native input ref and parses a Russian keyboard date', () => {
    const ref = createRef<HTMLInputElement>()
    const onChange = vi.fn()
    render(<DateInput ref={ref} label="Дата" id="date" value="2026-10-01" onChange={onChange} />)
    const input = screen.getByLabelText('Дата')
    expect(ref.current).toBe(input)
    expect(input).toHaveValue('01.10.2026')
    fireEvent.change(input, { target: { value: '05.10.2026' } })
    expect(onChange).toHaveBeenLastCalledWith('2026-10-05')
    fireEvent.change(input, { target: { value: '' } })
    expect(onChange).toHaveBeenLastCalledWith(null)
  })
})
