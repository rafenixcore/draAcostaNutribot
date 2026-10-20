import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import type { ReactNode } from 'react'

// Mock the API module
vi.mock('../services/api', () => ({
  getStoredToken: vi.fn(() => null),
  setStoredToken: vi.fn(),
  loginRequest: vi.fn(),
  changePasswordRequest: vi.fn(),
  forgotPasswordRequest: vi.fn(),
  resetPasswordRequest: vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('starts with no token and no session', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.token).toBeNull()
    expect(result.current.session).toBeNull()
    expect(result.current.portal).toBeNull()
  })

  it('logout clears session', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    act(() => {
      result.current.logout()
    })
    expect(result.current.token).toBeNull()
    expect(result.current.session).toBeNull()
    expect(result.current.portal).toBeNull()
  })

  it('login calls loginRequest and updates session', async () => {
    const { loginRequest } = await import('../services/api')
    const mockLoginRequest = vi.mocked(loginRequest)
    mockLoginRequest.mockResolvedValue({
      access_token: 'mock-token',
      role: 'doctor',
      must_change_password: false,
    })

    const { getStoredToken } = await import('../services/api')
    vi.mocked(getStoredToken).mockReturnValue('mock-token')

    const { result } = renderHook(() => useAuth(), { wrapper })

    await act(async () => {
      await result.current.login('test@test.com', 'password123')
    })

    expect(mockLoginRequest).toHaveBeenCalledWith('test@test.com', 'password123', undefined)
    expect(result.current.token).toBe('mock-token')
    expect(result.current.session?.role).toBe('doctor')
    expect(result.current.session?.mustChangePassword).toBe(false)
  })

  it('forgotPassword calls the API', async () => {
    const { forgotPasswordRequest } = await import('../services/api')
    const mockRequest = vi.mocked(forgotPasswordRequest)
    mockRequest.mockResolvedValue({ ok: true, message: 'Email sent' })

    const { result } = renderHook(() => useAuth(), { wrapper })

    let response
    await act(async () => {
      response = await result.current.forgotPassword('test@test.com')
    })

    expect(mockRequest).toHaveBeenCalledWith('test@test.com')
    expect(response).toEqual({ ok: true, message: 'Email sent' })
  })
})
