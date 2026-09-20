import type { Finding, FindingAnalysisResult, ReproductionResult, Test, TestSummaryAnalysis } from '../types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(body.detail ?? body.message ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request<{ status: string; service: string }>('/health'),

  createTest: (url: string, platform = 'web', config?: Record<string, any>) =>
    request<Test>('/tests', {
      method: 'POST',
      body: JSON.stringify({ url, platform, config }),
    }),

  listTests: () => request<Test[]>('/tests'),

  getTest: (id: string) => request<Test>(`/tests/${id}`),

  startTest: (id: string) =>
    request<{ status: string; test_id: string }>(`/tests/${id}/start`, {
      method: 'POST',
    }),

  cancelTest: (id: string) =>
    request<{ status: string; test_id: string }>(`/tests/${id}/cancel`, {
      method: 'POST',
    }),

  reproduceFinding: (
    testId: string,
    findingId: string,
    attempts = 1,
    actionSequence?: string[]
  ) =>
    request<ReproductionResult>(`/tests/${testId}/findings/${findingId}/reproduce`, {
      method: 'POST',
      body: JSON.stringify({ attempts, action_sequence: actionSequence }),
    }),

  getReproductions: (testId: string, findingId: string) =>
    request<ReproductionResult[]>(`/tests/${testId}/findings/${findingId}/reproductions`),

  getFinding: (testId: string, findingId: string) =>
    request<Finding>(`/tests/${testId}/findings/${findingId}`),

  analyzeFinding: (testId: string, findingId: string) =>
    request<FindingAnalysisResult>(`/tests/${testId}/findings/${findingId}/analyze`, {
      method: 'POST',
    }),

  analyzeTest: (testId: string) =>
    request<TestSummaryAnalysis>(`/tests/${testId}/analyze`, {
      method: 'POST',
    }),
}
