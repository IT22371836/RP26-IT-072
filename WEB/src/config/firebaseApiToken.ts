import { getCurrentFirebaseIdToken } from './firebase';

/** Return the current Firebase ID token for an authorized ML API request. */
export async function requireFirebaseApiToken(forceRefresh = false): Promise<string> {
  return getCurrentFirebaseIdToken(forceRefresh);
}
