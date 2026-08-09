import { backendApi } from '../config/api';
import type { ProviderPrivateDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';
import {
  fetchProviders as fetchFirebaseProviders,
  toggleProviderVerification as toggleFirebaseProviderVerification
} from '../config/firebase';
import type { Provider } from '../config/firebase';
import { runtimeConfig } from '../config/runtime';
import { mergeProviderProfile } from './provider-service';

function providerFromBackend(profile: ProviderPrivateDto): Provider {
  const base: Provider = {
    id: profile.provider_id,
    backendProviderId: profile.provider_id,
    fullName: profile.provider_name,
    email: profile.email || '',
    role: 'provider',
    phone: profile.phone || '',
    district: profile.district,
    city: profile.city,
    location: profile.location || { latitude: 0, longitude: 0 },
    providerImage: profile.provider_image || undefined,
    preferredLanguage: profile.preferred_language,
    createdAt: profile.created_at,
    createdTimestamp: Date.parse(profile.created_at),
    category: profile.category,
    experienceYears: profile.experience_years,
    skills: profile.skills,
    description: profile.description,
    verified: profile.verified
  };
  return mergeProviderProfile(base, profile);
}

export async function listAdminProvidersForConfiguredSource(): Promise<Provider[]> {
  if (runtimeConfig.dataSource === 'firebase') return fetchFirebaseProviders();

  const backendProfiles = await backendApi.listAdminProviders(await requireFirebaseApiToken());
  if (runtimeConfig.dataSource === 'fastapi') {
    return backendProfiles.map(providerFromBackend);
  }

  const firebaseProviders = await fetchFirebaseProviders();
  const byEmail = new Map(
    firebaseProviders.map((provider) => [provider.email.trim().toLowerCase(), provider])
  );
  const merged = backendProfiles.map((profile) => {
    const firebaseProvider = profile.email
      ? byEmail.get(profile.email.trim().toLowerCase())
      : undefined;
    if (profile.email) byEmail.delete(profile.email.trim().toLowerCase());
    return firebaseProvider
      ? mergeProviderProfile(firebaseProvider, profile)
      : providerFromBackend(profile);
  });
  return [...merged, ...byEmail.values()];
}

export async function setProviderVerificationForConfiguredSource(
  provider: Provider,
  verified: boolean
): Promise<Provider> {
  if (runtimeConfig.dataSource === 'firebase') {
    if (!provider.id) throw new Error('Provider Firebase identity is missing.');
    await toggleFirebaseProviderVerification(provider.id, verified);
    return {
      ...provider,
      verified,
      documents: {
        ...(provider.documents || {}),
        status: false,
        verified
      }
    };
  }

  const backendProviderId = provider.backendProviderId ||
    (runtimeConfig.dataSource === 'fastapi' ? provider.id : undefined);
  if (!backendProviderId) {
    throw new Error('This Firebase provider is not linked to a FastAPI provider ID.');
  }
  const profile = await backendApi.setAdminProviderVerification(
    await requireFirebaseApiToken(),
    backendProviderId,
    verified,
    verified ? 'Approved through WEB administrator review' : 'Revoked through WEB administrator review'
  );
  const updated = mergeProviderProfile(provider, profile);

  if (runtimeConfig.dataSource === 'hybrid') {
    if (!provider.id) throw new Error('Provider Firebase identity is missing.');
    await toggleFirebaseProviderVerification(provider.id, verified);
  }
  return updated;
}
