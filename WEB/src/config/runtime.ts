export type DataSource = 'firebase' | 'hybrid' | 'fastapi';
export type FileStorageSource = 'firebase' | 'backend';

function readEnum<T extends string>(
  name: string,
  value: string | undefined,
  allowed: readonly T[],
  fallback: T
): T {
  if (!value) return fallback;
  if ((allowed as readonly string[]).includes(value)) return value as T;
  throw new Error(`${name} must be one of: ${allowed.join(', ')}`);
}

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  const currentHost = typeof window === 'undefined' ? '127.0.0.1' : window.location.hostname;
  const currentProtocol = typeof window === 'undefined' ? 'http:' : window.location.protocol;
  const base = (configured || `${currentProtocol}//${currentHost}:8001`).replace(/\/+$/, '');
  return base.endsWith('/api/v1') ? base : `${base}/api/v1`;
}

export const runtimeConfig = Object.freeze({
  apiBaseUrl: apiBaseUrl(),
  dataSource: readEnum<DataSource>(
    'VITE_DATA_SOURCE',
    import.meta.env.VITE_DATA_SOURCE,
    ['firebase', 'hybrid', 'fastapi'],
    'firebase'
  ),
  authSource: 'firebase' as const,
  fileStorageSource: readEnum<FileStorageSource>(
    'VITE_FILE_STORAGE_SOURCE',
    import.meta.env.VITE_FILE_STORAGE_SOURCE,
    ['firebase', 'backend'],
    'firebase'
  )
});
