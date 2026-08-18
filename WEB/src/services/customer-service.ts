import { backendApi } from '../config/api';
import type { CustomerProfileDto, CustomerProfileUpdateDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';
import { updateCustomerProfile as updateFirebaseCustomerProfile } from '../config/firebase';
import type { Customer } from '../config/firebase';
import { runtimeConfig } from '../config/runtime';

function mergeProfile(current: Customer, profile: CustomerProfileDto): Customer {
  return {
    ...current,
    phone: profile.phone ?? current.phone,
    district: profile.district ?? current.district,
    city: profile.city ?? current.city,
    preferredLanguage: profile.preferred_language || current.preferredLanguage,
    location: profile.location ?? current.location,
    customerImage: profile.customer_image ?? current.customerImage
  };
}

function toBackendUpdate(updates: Partial<Customer>): CustomerProfileUpdateDto {
  return {
    phone: updates.phone,
    district: updates.district,
    city: updates.city,
    preferred_language: updates.preferredLanguage,
    location: updates.location,
    customer_image: updates.customerImage
  };
}

async function updateFastApiCustomer(
  current: Customer,
  updates: Partial<Customer>
): Promise<Customer> {
  if (updates.fullName && updates.fullName !== current.fullName) {
    throw new Error('Full-name updates still require Firebase until the backend user endpoint is added.');
  }
  if (updates.customerImage?.startsWith('data:')) {
    throw new Error('Upload the customer image to configured file storage before FastAPI profile update.');
  }
  const profile = await backendApi.updateCustomerProfile(
    await requireFirebaseApiToken(),
    toBackendUpdate(updates)
  );
  return mergeProfile({ ...current, ...updates }, profile);
}

export async function syncCustomerProfileFromConfiguredSource(
  current: Customer
): Promise<Customer> {
  if (runtimeConfig.dataSource === 'firebase') return current;
  const profile = await backendApi.getCustomerProfile(await requireFirebaseApiToken());
  return mergeProfile(current, profile);
}

export async function updateCustomerProfileForConfiguredSource(
  current: Customer,
  updates: Partial<Customer>
): Promise<Customer> {
  if (!current.id) throw new Error('Customer Firebase identity is missing.');

  if (runtimeConfig.dataSource === 'firebase') {
    return updateFirebaseCustomerProfile(current.id, updates);
  }
  if (runtimeConfig.dataSource === 'fastapi') {
    return updateFastApiCustomer(current, updates);
  }

  // During hybrid mode Firebase remains authoritative and the backend is an explicit shadow write.
  const firebaseCustomer = await updateFirebaseCustomerProfile(current.id, updates);
  return updateFastApiCustomer(firebaseCustomer, {
    ...updates,
    customerImage: firebaseCustomer.customerImage
  });
}
