const env = import.meta.env

export const config = {
  apiUrl: (env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000',
  useMocks: (env.VITE_USE_MOCKS ?? 'true') !== 'false',
  productName: (env.VITE_PRODUCT_NAME as string | undefined) || 'ScamSathi',
  personaName: (env.VITE_PERSONA_NAME as string | undefined) || 'Ajji',
} as const
