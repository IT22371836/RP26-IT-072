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

export const runtimeConfig = Object.freeze({
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1').replace(/\/$/, ''),
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
