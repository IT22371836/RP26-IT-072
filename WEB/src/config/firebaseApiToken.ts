import { getCurrentFirebaseIdToken } from './firebase';

/** Return the current Firebase ID token for an authorized ML API request. */
export async function requireFirebaseApiToken(): Promise<string> {
  return getCurrentFirebaseIdToken();
}
