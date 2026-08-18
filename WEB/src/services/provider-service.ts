import { backendApi } from '../config/api';
import type {
  ProviderPrivateDto,
  ProviderDocumentCategoryDto,
  ProviderDocumentItemDto,
  ProviderProfileUpdateDto,
  ProviderWorkingHoursDto
} from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';
import {
  deleteProviderDocument as deleteFirebaseProviderDocument,
  requestDocumentVerification as requestFirebaseDocumentVerification,
  updateProviderProfile as updateFirebaseProviderProfile,
  uploadProviderDocument,
  uploadProviderDocumentFile
} from '../config/firebase';
import type {
  DaySchedule,
  Provider,
  ProviderDocumentItem,
  ProviderDocuments,
  WorkingHours
} from '../config/firebase';
import { runtimeConfig } from '../config/runtime';

const DAY_MAPPINGS = [
  ['Monday', 'monday'],
  ['Tuesday', 'tuesday'],
  ['Wednesday', 'wednesday'],
  ['Thursday', 'thursday'],
  ['Friday', 'friday'],
  ['Saturday', 'saturday'],
  ['Sunday', 'sunday']
] as const;

export type WebProviderDocumentCategory =
  | 'identityDocument'
  | 'certification'
  | 'businessRegistration'
  | 'experienceProof'
  | 'portfolioWork';

const DOCUMENT_CATEGORY_MAPPINGS: Record<
  WebProviderDocumentCategory,
  ProviderDocumentCategoryDto
> = {
  identityDocument: 'identity_document',
  certification: 'certification',
  businessRegistration: 'business_registration',
  experienceProof: 'experience_proof',
  portfolioWork: 'portfolio_work'
};

function toWebDocument(item: ProviderDocumentItemDto): ProviderDocumentItem {
  return {
    fileId: item.file_id,
    fileName: item.file_name,
    fileUrl: item.current_url || item.file_url,
    legacyUrl: item.legacy_url || undefined,
    currentUrl: item.current_url || undefined,
    storagePath: item.storage_path || undefined,
    contentSha256: item.content_sha256 || undefined,
    contentType: item.content_type || undefined,
    sizeBytes: item.size_bytes ?? undefined,
    format: item.format,
    uploadedAt: item.uploaded_at
  };
}

function mergeDocuments(
  current: ProviderDocuments | undefined,
  profile: ProviderPrivateDto
): ProviderDocuments {
  const backendDocuments = profile.documents;
  const merged: ProviderDocuments = {
    ...(current || {}),
    status: backendDocuments.status,
    verified: backendDocuments.verified
  };
  for (const [webCategory, apiCategory] of Object.entries(DOCUMENT_CATEGORY_MAPPINGS) as [
    WebProviderDocumentCategory,
    ProviderDocumentCategoryDto
  ][]) {
    const currentItems = current?.[webCategory] || [];
    const backendItems = backendDocuments[apiCategory]
      .filter((item) => item.deleted_at === null)
      .map(toWebDocument);
    merged[webCategory] = Array.from(
      new Map([...currentItems, ...backendItems].map((item) => [item.fileId, item])).values()
    );
  }
  return merged;
}

function toBackendWorkingHours(value: WorkingHours): ProviderWorkingHoursDto {
  return Object.fromEntries(
    DAY_MAPPINGS.map(([webDay, apiDay]) => {
      const schedule = value[webDay];
      return [apiDay, {
        is_open: schedule.isOpen,
        start: schedule.start,
        end: schedule.end
      }];
    })
  ) as unknown as ProviderWorkingHoursDto;
}

function fromBackendWorkingHours(value: ProviderWorkingHoursDto): WorkingHours {
  return Object.fromEntries(
    DAY_MAPPINGS.map(([webDay, apiDay]) => {
      const schedule = value[apiDay];
      const webSchedule: DaySchedule = {
        isOpen: schedule.is_open,
        start: schedule.start,
        end: schedule.end
      };
      return [webDay, webSchedule];
    })
  ) as unknown as WorkingHours;
}

export function mergeProviderProfile(
  current: Provider,
  profile: ProviderPrivateDto
): Provider {
  return {
    ...current,
    backendProviderId: profile.provider_id,
    email: profile.email ?? current.email,
    fullName: profile.provider_name,
    category: profile.category,
    district: profile.district,
    city: profile.city,
    experienceYears: profile.experience_years,
    skills: profile.skills,
    description: profile.description,
    phone: profile.phone ?? current.phone,
    location: profile.location ?? current.location,
    providerImage: profile.provider_image ?? current.providerImage,
    preferredLanguage: profile.preferred_language || current.preferredLanguage,
    nic: profile.nic ?? current.nic,
    workingHours: profile.working_hours
      ? fromBackendWorkingHours(profile.working_hours)
      : current.workingHours,
    verified: profile.verified,
    documents: mergeDocuments(current.documents, profile)
  };
}

function toBackendUpdate(updates: Partial<Provider>): ProviderProfileUpdateDto {
  return {
    provider_name: updates.fullName,
    category: updates.category,
    district: updates.district,
    city: updates.city,
    experience_years: updates.experienceYears,
    skills: updates.skills,
    description: updates.description,
    phone: updates.phone,
    location: updates.location,
    provider_image: updates.providerImage,
    preferred_language: updates.preferredLanguage,
    nic: updates.nic,
    working_hours: updates.workingHours
      ? toBackendWorkingHours(updates.workingHours)
      : undefined
  };
}

async function updateFastApiProvider(
  current: Provider,
  updates: Partial<Provider>
): Promise<Provider> {
  if (updates.providerImage?.startsWith('data:')) {
    throw new Error('Upload the provider image to configured file storage before FastAPI profile update.');
  }
  const profile = await backendApi.updateProviderProfile(
    await requireFirebaseApiToken(),
    toBackendUpdate(updates)
  );
  return mergeProviderProfile({ ...current, ...updates }, profile);
}

export async function syncProviderProfileFromConfiguredSource(
  current: Provider
): Promise<Provider> {
  if (runtimeConfig.dataSource === 'firebase') return current;
  const profile = await backendApi.getProviderProfile(await requireFirebaseApiToken());
  return mergeProviderProfile(current, profile);
}

export async function updateProviderProfileForConfiguredSource(
  current: Provider,
  updates: Partial<Provider>
): Promise<Provider> {
  if (!current.id) throw new Error('Provider Firebase identity is missing.');

  if (runtimeConfig.dataSource === 'firebase') {
    return updateFirebaseProviderProfile(current.id, updates);
  }
  if (runtimeConfig.dataSource === 'fastapi') {
    return updateFastApiProvider(current, updates);
  }

  const firebaseProvider = await updateFirebaseProviderProfile(current.id, updates);
  return updateFastApiProvider(firebaseProvider, {
    ...updates,
    providerImage: firebaseProvider.providerImage
  });
}

function addDocumentLocally(
  current: Provider,
  category: WebProviderDocumentCategory,
  item: ProviderDocumentItem
): Provider {
  const documents = current.documents || {};
  return {
    ...current,
    documents: {
      ...documents,
      [category]: [...(documents[category] || []), item]
    }
  };
}

function removeDocumentLocally(
  current: Provider,
  category: WebProviderDocumentCategory,
  fileId: string
): Provider {
  const documents = current.documents || {};
  return {
    ...current,
    documents: {
      ...documents,
      [category]: (documents[category] || []).filter((item) => item.fileId !== fileId)
    }
  };
}

export async function uploadProviderDocumentForConfiguredSource(
  current: Provider,
  category: WebProviderDocumentCategory,
  fileName: string,
  fileDataUrl: string
): Promise<Provider> {
  if (!current.id) throw new Error('Provider Firebase identity is missing.');

  if (runtimeConfig.fileStorageSource === 'backend') {
    const profile = await backendApi.uploadProviderDocument(
      await requireFirebaseApiToken(),
      DOCUMENT_CATEGORY_MAPPINGS[category],
      { file_name: fileName, data_url: fileDataUrl }
    );
    return mergeProviderProfile(current, profile);
  }

  const item = runtimeConfig.dataSource === 'fastapi'
    ? await uploadProviderDocumentFile(current.id, fileName, fileDataUrl)
    : await uploadProviderDocument(current.id, category, fileName, fileDataUrl);
  const withFirebaseDocument = addDocumentLocally(current, category, item);
  if (runtimeConfig.dataSource === 'firebase') return withFirebaseDocument;

  const profile = await backendApi.addProviderDocument(
    await requireFirebaseApiToken(),
    DOCUMENT_CATEGORY_MAPPINGS[category],
    {
      file_id: item.fileId,
      file_name: item.fileName,
      file_url: item.fileUrl,
      format: item.format as 'JPG' | 'PNG' | 'PDF'
    }
  );
  return mergeProviderProfile(withFirebaseDocument, profile);
}

function openBlob(blob: Blob): void {
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function openProviderDocumentForConfiguredSource(
  provider: Provider,
  category: WebProviderDocumentCategory,
  item: ProviderDocumentItem,
  asAdministrator = false
): Promise<void> {
  const managedPrivateObject = (item.currentUrl || item.fileUrl).startsWith('gs://');
  if (!managedPrivateObject) {
    window.open(item.legacyUrl || item.currentUrl || item.fileUrl, '_blank', 'noopener,noreferrer');
    return;
  }
  const token = await requireFirebaseApiToken();
  const blob = asAdministrator
    ? await backendApi.downloadAdminProviderDocument(
        token,
        provider.backendProviderId || provider.id || '',
        DOCUMENT_CATEGORY_MAPPINGS[category],
        item.fileId
      )
    : await backendApi.downloadProviderDocument(
        token,
        DOCUMENT_CATEGORY_MAPPINGS[category],
        item.fileId
      );
  openBlob(blob);
}

export async function deleteProviderDocumentForConfiguredSource(
  current: Provider,
  category: WebProviderDocumentCategory,
  fileId: string
): Promise<Provider> {
  if (!current.id) throw new Error('Provider Firebase identity is missing.');
  if (runtimeConfig.dataSource !== 'fastapi') {
    await deleteFirebaseProviderDocument(current.id, category, fileId);
  }
  const withoutDocument = removeDocumentLocally(current, category, fileId);
  if (runtimeConfig.dataSource === 'firebase') return withoutDocument;

  const profile = await backendApi.deleteProviderDocument(
    await requireFirebaseApiToken(),
    DOCUMENT_CATEGORY_MAPPINGS[category],
    fileId
  );
  return mergeProviderProfile(withoutDocument, profile);
}

export async function requestProviderVerificationForConfiguredSource(
  current: Provider
): Promise<Provider> {
  if (!current.id) throw new Error('Provider Firebase identity is missing.');
  if (runtimeConfig.dataSource !== 'fastapi') {
    await requestFirebaseDocumentVerification(current.id, current.documents);
  }
  const withRequestStatus: Provider = {
    ...current,
    documents: { ...(current.documents || {}), status: true }
  };
  if (runtimeConfig.dataSource === 'firebase') return withRequestStatus;
  const profile = await backendApi.requestProviderDocumentVerification(
    await requireFirebaseApiToken()
  );
  return mergeProviderProfile(withRequestStatus, profile);
}
