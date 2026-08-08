import { initializeApp, getApps, getApp } from "firebase/app";
import { 
  getDatabase, 
  ref, 
  push, 
  set, 
  get, 
  child,
  update
} from "firebase/database";
import { 
  getStorage, 
  ref as storageRef, 
  uploadString, 
  getDownloadURL 
} from "firebase/storage";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  onAuthStateChanged
} from "firebase/auth";

import rtdbSeedData from "../data/service-e333a-default-rtdb-export.json";

// Default Firebase Configuration matching the project RTDB export
const defaultFirebaseConfig = {
  apiKey: "AIzaSyB-iFnd0U1xASrgy4YZLv4GFHFwytF9ua0",
  authDomain: "service-e333a.firebaseapp.com",
  databaseURL: "https://service-e333a-default-rtdb.firebaseio.com",
  projectId: "service-e333a",
  storageBucket: "service-e333a.firebasestorage.app",
  messagingSenderId: "436492949883",
  appId: "1:436492949883:web:39d71c8ef622c4d5e885de",
  measurementId: "G-9F0L8RHFS1"
};

// Allow runtime overrides via localStorage or environment variables
export const getStoredFirebaseConfig = () => {
  try {
    const saved = localStorage.getItem("custom_firebase_config");
    if (saved) return JSON.parse(saved);
  } catch (e) {
    console.warn("Could not parse saved Firebase config", e);
  }
  return {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || defaultFirebaseConfig.apiKey,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || defaultFirebaseConfig.authDomain,
    databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL || defaultFirebaseConfig.databaseURL,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || defaultFirebaseConfig.projectId,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || defaultFirebaseConfig.storageBucket,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || defaultFirebaseConfig.messagingSenderId,
    appId: import.meta.env.VITE_FIREBASE_APP_ID || defaultFirebaseConfig.appId,
  };
};

const firebaseConfig = getStoredFirebaseConfig();

export const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const db = getDatabase(app);
export const storage = getStorage(app);
export const auth = getAuth(app);

// Helper function to upload images to Firebase Storage under folder/entityId/
export async function uploadImageToStorage(
  folder: 'customers' | 'providers',
  entityId: string,
  imageData: string
): Promise<string> {
  if (!imageData) return '';
  
  if (imageData.startsWith('http://') || imageData.startsWith('https://')) {
    return imageData;
  }

  if (imageData.startsWith('data:image/')) {
    try {
      const fileName = `profile_${Date.now().toString().slice(-4)}.png`;
      const filePath = `${folder}/${entityId}/${fileName}`;
      const imgRef = storageRef(storage, filePath);
      
      const snapshot = await uploadString(imgRef, imageData, 'data_url');
      const downloadUrl = await getDownloadURL(snapshot.ref);
      return downloadUrl;
    } catch (err) {
      console.warn(`Firebase Storage upload fallback for ${folder}/${entityId}:`, err);
      return `https://firebasestorage.googleapis.com/v0/b/${firebaseConfig.storageBucket}/o/${folder}%2F${entityId}%2Fprofile.png?alt=media`;
    }
  }

  return imageData;
}

// Data types matching service-e333a-default-rtdb-export.json
export interface LocationCoords {
  latitude: number;
  longitude: number;
}

export interface Customer {
  id?: string;
  fullName: string;
  email: string;
  role: "customer";
  phone: string;
  district: string;
  city: string;
  location: LocationCoords;
  customerImage: string;
  preferredLanguage: string;
  createdAt: string;
  createdTimestamp: number;
}

export interface DaySchedule {
  isOpen: boolean;
  start: string;
  end: string;
}

export interface WorkingHours {
  Monday: DaySchedule;
  Tuesday: DaySchedule;
  Wednesday: DaySchedule;
  Thursday: DaySchedule;
  Friday: DaySchedule;
  Saturday: DaySchedule;
  Sunday: DaySchedule;
}

export const DEFAULT_WORKING_HOURS: WorkingHours = {
  Monday: { isOpen: true, start: "08:00 AM", end: "06:00 PM" },
  Tuesday: { isOpen: true, start: "08:00 AM", end: "06:00 PM" },
  Wednesday: { isOpen: true, start: "08:00 AM", end: "06:00 PM" },
  Thursday: { isOpen: true, start: "08:00 AM", end: "06:00 PM" },
  Friday: { isOpen: true, start: "08:00 AM", end: "06:00 PM" },
  Saturday: { isOpen: true, start: "08:00 AM", end: "01:00 PM" },
  Sunday: { isOpen: false, start: "", end: "" }
};

export interface ProviderDocumentItem {
  fileId: string;
  fileName: string;
  fileUrl: string;
  legacyUrl?: string;
  currentUrl?: string;
  storagePath?: string;
  contentSha256?: string;
  contentType?: string;
  sizeBytes?: number;
  format: string; // 'JPG' | 'PNG' | 'PDF'
  uploadedAt: string;
}

export interface CredibilityInfo {
  credibilityScore?: number;
  credibilityLevel?: string;
  lastEvaluatedAt?: string;
}

export interface ExtractedFeatures {
  provider_id?: string;
  service_category?: string;
  identity_verified?: number;
  certification_count?: number;
  highest_cert_level?: string;
  cert_issuer_reputation?: number;
  business_registered?: number;
  experience_years?: number;
  experience_reference_count?: number;
  portfolio_quality_score?: number;
  portfolio_count?: number;
  credibility?: CredibilityInfo;
}

export interface ProviderDocuments {
  status?: boolean;
  verified?: boolean;
  identityDocument?: ProviderDocumentItem[];
  certification?: ProviderDocumentItem[];
  businessRegistration?: ProviderDocumentItem[];
  experienceProof?: ProviderDocumentItem[];
  portfolioWork?: ProviderDocumentItem[];
  extractedFeatures?: ExtractedFeatures;
  credibility?: CredibilityInfo;
}

export interface Provider {
  id?: string;
  backendProviderId?: string;
  fullName: string;
  email: string;
  role: "provider";
  phone: string;
  district: string;
  city: string;
  location: LocationCoords;
  providerImage?: string;
  preferredLanguage: string;
  createdAt: string;
  createdTimestamp: number;
  nic?: string;
  category?: string;
  experienceYears?: number;
  skills?: string[];
  description?: string;
  workingHours?: WorkingHours;
  documents?: ProviderDocuments;
  extractedFeatures?: ExtractedFeatures;
  credibility?: CredibilityInfo;
  uid?: string;
  verified?: boolean;
}

export interface AdminUser {
  id: string;
  fullName: string;
  email: string;
  role: "admin";
  phone: string;
  district: string;
  city: string;
  location: LocationCoords;
  customerImage: string;
  preferredLanguage: string;
  createdAt: string;
  createdTimestamp: number;
}

export interface EvaluatedProvider {
  provider_id: string;
  provider_name: string;
  provider_location?: LocationCoords;
  distance_km?: number;
  is_available?: boolean;
  location_type?: string;
  recommendation?: string;
  service_day?: string;
  user_id?: string;
  weather_risk?: string;
  working_hours_status?: string;
}

export interface OutputResults {
  evaluated_at?: string;
  evaluated_providers?: EvaluatedProvider[];
  provider_ids?: string[];
  recommendation?: string;
  weather_risk?: string;
  weather_summary?: string;
}

export interface FilterRequestItem {
  id?: string;
  request_id: string;
  user_id: string;
  service_date?: string;
  service_time?: {
    start_time?: string;
    end_time?: string;
  };
  location_type?: string;
  isNewRequest?: boolean;
  output_results?: OutputResults;
  results?: {
    provider_ids?: string[];
  };
}

const LOCAL_STORAGE_CUSTOMERS_KEY = "sliit_rtdb_fallback_customers";
const LOCAL_STORAGE_PROVIDERS_KEY = "sliit_rtdb_fallback_providers";
const LOCAL_STORAGE_FILTER_REQUESTS_KEY = "sliit_rtdb_fallback_filter_requests";
export const ACTIVE_SESSION_KEY = "sliit_active_user_session";

// RTDB + Firebase Auth Customer Registration
export async function registerCustomer(
  data: Omit<Customer, "role" | "createdAt" | "createdTimestamp">,
  password?: string
): Promise<Customer> {
  const now = new Date();
  let authUid = "";

  if (password) {
    try {
      const userCred = await createUserWithEmailAndPassword(auth, data.email, password);
      authUid = userCred.user.uid;
    } catch (authErr: any) {
      console.warn("Firebase Auth sign up info:", authErr.message);
    }
  }

  const customersRef = ref(db, "customers");
  const newRef = push(customersRef);
  const key = authUid || newRef.key || ("-OyZp" + Math.random().toString(36).substring(2, 11));

  let finalImageUrl = data.customerImage;
  if (finalImageUrl) {
    finalImageUrl = await uploadImageToStorage('customers', key, finalImageUrl);
  }

  if (auth.currentUser) {
    try {
      await updateProfile(auth.currentUser, {
        displayName: data.fullName,
        photoURL: finalImageUrl
      });
    } catch (e) {
      console.warn("Could not update auth display profile", e);
    }
  }

  const newCustomer: Customer = {
    ...data,
    id: key,
    role: "customer",
    customerImage: finalImageUrl,
    createdAt: now.toISOString(),
    createdTimestamp: now.getTime()
  };
  delete (newCustomer as any).uid;

  try {
    await set(ref(db, `customers/${key}`), newCustomer);
    saveToLocalBackup(LOCAL_STORAGE_CUSTOMERS_KEY, key, newCustomer);
    return newCustomer;
  } catch (error) {
    console.warn("Firebase RTDB operation failed, using local storage fallback:", error);
    saveToLocalBackup(LOCAL_STORAGE_CUSTOMERS_KEY, key, newCustomer);
    return newCustomer;
  }
}

// RTDB + Firebase Auth Provider Registration
export async function registerProvider(
  data: Omit<Provider, "role" | "createdAt" | "createdTimestamp" | "verified">,
  password?: string
): Promise<Provider> {
  const now = new Date();
  let authUid = "";

  if (password) {
    try {
      const userCred = await createUserWithEmailAndPassword(auth, data.email, password);
      authUid = userCred.user.uid;
    } catch (authErr: any) {
      console.warn("Firebase Auth sign up info:", authErr.message);
    }
  }

  const providersRef = ref(db, "providers");
  const newRef = push(providersRef);
  const key = authUid || newRef.key || ("-OyZpr" + Math.random().toString(36).substring(2, 11));

  let rawImage = data.providerImage || '';
  let finalImageUrl = rawImage;
  if (rawImage) {
    finalImageUrl = await uploadImageToStorage('providers', key, rawImage);
  }

  if (auth.currentUser) {
    try {
      await updateProfile(auth.currentUser, {
        displayName: data.fullName,
        photoURL: finalImageUrl
      });
    } catch (e) {
      console.warn("Could not update auth display profile", e);
    }
  }

  // Initial Provider Registration sets verified: false and default workingHours
  const newProvider: Provider = {
    ...data,
    id: key,
    uid: key,
    role: "provider",
    providerImage: finalImageUrl,
    workingHours: data.workingHours || DEFAULT_WORKING_HOURS,
    createdAt: now.toISOString(),
    createdTimestamp: now.getTime(),
    verified: false
  };
  delete (newProvider as any).customerImage;

  try {
    await set(ref(db, `providers/${key}`), newProvider);
    saveToLocalBackup(LOCAL_STORAGE_PROVIDERS_KEY, key, newProvider);
    return newProvider;
  } catch (error) {
    console.warn("Firebase RTDB operation failed, using local storage fallback:", error);
    saveToLocalBackup(LOCAL_STORAGE_PROVIDERS_KEY, key, newProvider);
    return newProvider;
  }
}

// Helper to check if any document exists in documents node
export function hasUploadedDocuments(docs?: ProviderDocuments): boolean {
  if (!docs) return false;
  const categories: (keyof ProviderDocuments)[] = [
    'identityDocument',
    'certification',
    'businessRegistration',
    'experienceProof',
    'portfolioWork'
  ];
  return categories.some(cat => {
    const list = docs[cat];
    return Array.isArray(list) && list.length > 0;
  });
}

// Helper to count total uploaded documents across all categories
export function getUploadedDocumentCount(docs?: ProviderDocuments): number {
  if (!docs) return 0;
  const categories: (keyof ProviderDocuments)[] = [
    'identityDocument',
    'certification',
    'businessRegistration',
    'experienceProof',
    'portfolioWork'
  ];
  return categories.reduce((total, cat) => {
    const list = docs[cat];
    return total + (Array.isArray(list) ? list.length : 0);
  }, 0);
}

// Request Document Verification by Provider (sets documents/status: true)
export async function requestDocumentVerification(providerId: string, docs?: ProviderDocuments): Promise<void> {
  if (docs && !hasUploadedDocuments(docs)) {
    throw new Error("No documents uploaded. You must upload at least one verification document before requesting document verification.");
  }

  try {
    const provRef = ref(db, `providers/${providerId}`);
    await update(provRef, { "documents/status": true });
  } catch (err) {
    console.warn("RTDB update document status failed, updating local backup:", err);
  }

  const existingStr = localStorage.getItem(LOCAL_STORAGE_PROVIDERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  if (existing[providerId]) {
    if (!existing[providerId].documents) existing[providerId].documents = {};
    existing[providerId].documents.status = true;
    localStorage.setItem(LOCAL_STORAGE_PROVIDERS_KEY, JSON.stringify(existing));
  }
}

export function getProviderCredibility(p?: Provider | null): CredibilityInfo | undefined {
  if (!p) return undefined;
  return p.credibility || p.extractedFeatures?.credibility || p.documents?.credibility || (p.documents?.extractedFeatures as any)?.credibility;
}

export function getProviderExtractedFeatures(p?: Provider | null): ExtractedFeatures | undefined {
  if (!p) return undefined;
  return p.extractedFeatures || p.documents?.extractedFeatures;
}

export function generateExtractedFeaturesForProvider(provider: Provider): ExtractedFeatures {
  const docs = provider.documents || {};
  const identityCount = docs.identityDocument?.length || 0;
  const certCount = docs.certification?.length || 0;
  const brCount = docs.businessRegistration?.length || 0;
  const expCount = docs.experienceProof?.length || 0;
  const portCount = docs.portfolioWork?.length || 0;

  const identityVerified = identityCount > 0 ? 1 : 0;
  const businessRegistered = brCount > 0 ? 1 : 0;
  const expYears = provider.experienceYears || 5;
  const certRep = certCount > 0 ? 0.92 : 0.75;
  const portQuality = portCount > 0 ? 0.85 : 0.70;

  let score = 55;
  if (identityVerified) score += 15;
  if (businessRegistered) score += 15;
  score += Math.min(certCount * 4, 8);
  score += Math.min(expYears * 1.2, 7);
  score += Math.min(portCount * 2, 5);
  const credibilityScore = Math.min(Math.round(score * 100) / 100, 98.5);

  let credibilityLevel = "Basic";
  if (credibilityScore >= 90) credibilityLevel = "Expert";
  else if (credibilityScore >= 80) credibilityLevel = "Professional";
  else if (credibilityScore >= 65) credibilityLevel = "Verified";

  const credibility: CredibilityInfo = {
    credibilityScore,
    credibilityLevel,
    lastEvaluatedAt: new Date().toISOString()
  };

  return {
    provider_id: provider.id || provider.uid,
    service_category: provider.category || "General Service",
    identity_verified: identityVerified,
    certification_count: certCount,
    highest_cert_level: certCount > 0 ? "NVQ Level 4" : "Certified Specialist",
    cert_issuer_reputation: certRep,
    business_registered: businessRegistered,
    experience_years: expYears,
    experience_reference_count: Math.max(expCount, 1),
    portfolio_quality_score: portQuality,
    portfolio_count: portCount,
    credibility
  };
}

// Toggle Provider Verification Status by System Admin
export async function toggleProviderVerification(
  id: string,
  verified: boolean
): Promise<void> {
  const provRef = ref(db, `providers/${id}`);
  let extractedFeatures: ExtractedFeatures | undefined;
  let credibility: CredibilityInfo | undefined;

  try {
    const snapshot = await get(provRef);
    if (snapshot.exists()) {
      const current = snapshot.val();
      if (verified) {
        extractedFeatures = current.extractedFeatures || generateExtractedFeaturesForProvider({ id, ...current });
        credibility = extractedFeatures?.credibility || getProviderCredibility({ id, ...current }) || generateExtractedFeaturesForProvider({ id, ...current }).credibility;
        if (extractedFeatures) {
          extractedFeatures.credibility = credibility;
        }
      } else {
        extractedFeatures = current.extractedFeatures;
        credibility = current.credibility;
      }
    }

    const updatePayload: any = {
      verified,
      "documents/status": false,
      "documents/verified": verified
    };
    if (verified && extractedFeatures) {
      updatePayload.extractedFeatures = extractedFeatures;
    }

    await update(provRef, updatePayload);
  } catch (err) {
    console.warn("RTDB update verification failed, updating local backup:", err);
  }

  const existingStr = localStorage.getItem(LOCAL_STORAGE_PROVIDERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  if (existing[id]) {
    existing[id].verified = verified;
    if (!existing[id].documents) existing[id].documents = {};
    existing[id].documents.verified = verified;
    existing[id].documents.status = false;
    if (verified && extractedFeatures) {
      existing[id].extractedFeatures = extractedFeatures;
    }
    localStorage.setItem(LOCAL_STORAGE_PROVIDERS_KEY, JSON.stringify(existing));
  }
}

// Update existing Customer Profile
export async function updateCustomerProfile(
  id: string,
  updatedData: Partial<Customer>
): Promise<Customer> {
  if ('uid' in updatedData) {
    delete (updatedData as any).uid;
  }

  let finalImageUrl = updatedData.customerImage;
  if (finalImageUrl && finalImageUrl.startsWith('data:image/')) {
    finalImageUrl = await uploadImageToStorage('customers', id, finalImageUrl);
    updatedData.customerImage = finalImageUrl;
  }

  try {
    const custRef = ref(db, `customers/${id}`);
    await update(custRef, updatedData);
  } catch (err) {
    console.warn("RTDB update failed, updating local backup:", err);
  }

  const existingStr = localStorage.getItem(LOCAL_STORAGE_CUSTOMERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  const merged = { ...(existing[id] || {}), ...updatedData, id };
  existing[id] = merged;
  localStorage.setItem(LOCAL_STORAGE_CUSTOMERS_KEY, JSON.stringify(existing));

  return merged as Customer;
}

// Update existing Provider Profile
export async function updateProviderProfile(
  id: string,
  updatedData: Partial<Provider>
): Promise<Provider> {
  if ('customerImage' in updatedData) {
    delete (updatedData as any).customerImage;
  }

  let finalImageUrl = updatedData.providerImage;
  if (finalImageUrl && finalImageUrl.startsWith('data:image/')) {
    finalImageUrl = await uploadImageToStorage('providers', id, finalImageUrl);
    updatedData.providerImage = finalImageUrl;
  }

  try {
    const provRef = ref(db, `providers/${id}`);
    await update(provRef, updatedData);
  } catch (err) {
    console.warn("RTDB update failed, updating local backup:", err);
  }

  const existingStr = localStorage.getItem(LOCAL_STORAGE_PROVIDERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  const merged = { ...(existing[id] || {}), ...updatedData, id };
  existing[id] = merged;
  localStorage.setItem(LOCAL_STORAGE_PROVIDERS_KEY, JSON.stringify(existing));

  return merged as Provider;
}

// Fetch all customers from RTDB
export async function fetchCustomers(): Promise<Customer[]> {
  try {
    const snapshot = await get(child(ref(db), "customers"));
    if (snapshot.exists()) {
      const val = snapshot.val();
      return Object.keys(val).map(key => ({ id: key, ...val[key] }));
    }
  } catch (err) {
    console.warn("Fetching from RTDB failed, loading from local backup:", err);
  }
  return getLocalBackup<Customer>(LOCAL_STORAGE_CUSTOMERS_KEY);
}

// Fetch all providers from RTDB
export async function fetchProviders(): Promise<Provider[]> {
  try {
    const snapshot = await get(child(ref(db), "providers"));
    if (snapshot.exists()) {
      const val = snapshot.val();
      return Object.keys(val).map(key => ({ id: key, ...val[key] }));
    }
  } catch (err) {
    console.warn("Fetching providers from RTDB failed, loading local backup:", err);
  }
  return getLocalBackup<Provider>(LOCAL_STORAGE_PROVIDERS_KEY);
}

// Customer-facing Firebase reads must never expose private provider identity data.
export async function fetchPublicProviders(): Promise<Provider[]> {
  const providers = await fetchProviders();
  return providers.map(({ nic: _nic, documents: _documents, ...provider }) => provider);
}

// Fetch all ML filter requests from RTDB (or local backup / seed data)
export async function fetchFilterRequests(): Promise<FilterRequestItem[]> {
  try {
    const snapshot = await get(child(ref(db), "filter_requests"));
    if (snapshot.exists()) {
      const val = snapshot.val();
      return Object.keys(val).map(key => ({ id: key, request_id: val[key].request_id || key, ...val[key] }));
    }
  } catch (err) {
    console.warn("Fetching filter_requests from RTDB failed, loading local backup:", err);
  }

  const localBackup = getLocalBackup<FilterRequestItem>(LOCAL_STORAGE_FILTER_REQUESTS_KEY);
  if (localBackup.length > 0) {
    return localBackup;
  }

  if (rtdbSeedData.filter_requests) {
    const seedFR = Object.keys(rtdbSeedData.filter_requests).map(k => ({
      id: k,
      request_id: (rtdbSeedData.filter_requests as any)[k].request_id || k,
      ...(rtdbSeedData.filter_requests as any)[k]
    }));
    return seedFR;
  }

  return [];
}

// Helper to look up profile by email
export async function fetchUserProfileByEmail(email: string): Promise<any | null> {
  const clean = email.trim().toLowerCase();

  const customers = await fetchCustomers();
  const foundCust = customers.find(c => c.email.toLowerCase() === clean);
  if (foundCust) return { ...foundCust, role: "customer" };

  const providers = await fetchProviders();
  const foundProv = providers.find(p => p.email.toLowerCase() === clean);
  if (foundProv) return { ...foundProv, role: "provider" };

  return null;
}

// Firebase login is only for customer/provider transition identities.
export async function loginUser(
  emailOrPhone: string,
  password?: string
): Promise<any | null> {
  const cleanQuery = emailOrPhone.trim().toLowerCase();

  if (!password || password.trim().length === 0) {
    throw new Error("Password is required to log in. Please enter your account password.");
  }

  // Try Firebase Auth sign-in for customer/provider accounts.
  if (cleanQuery.includes('@')) {
    try {
      const userCred = await signInWithEmailAndPassword(auth, cleanQuery, password);
      const uid = userCred.user.uid;

      const custSnapshot = await get(child(ref(db), `customers/${uid}`));
      if (custSnapshot.exists()) {
        const custVal = custSnapshot.val();
        delete custVal.uid;
        return { id: uid, role: "customer", ...custVal };
      }

      const provSnapshot = await get(child(ref(db), `providers/${uid}`));
      if (provSnapshot.exists()) {
        return { id: uid, uid, role: "provider", ...provSnapshot.val() };
      }

      const profile = await fetchUserProfileByEmail(cleanQuery);
      if (profile) return profile;

    } catch (authErr: any) {
      console.warn("Firebase Auth login attempt error:", authErr.code, authErr.message);

      if (authErr.code === 'auth/wrong-password' || authErr.code === 'auth/invalid-credential') {
        throw new Error("Incorrect password. Please verify your password and try again.");
      }

      throw new Error("Invalid email or password. Please check your credentials or register a new account.");
    }
  }

  throw new Error("Invalid login details. Please check your email and password.");
}

export async function getCurrentFirebaseIdToken(): Promise<string> {
  if (!auth.currentUser) {
    throw new Error("A current Firebase session is required for account linking.");
  }
  return auth.currentUser.getIdToken(true);
}

export async function logoutFirebaseUser() {
  try {
    await signOut(auth);
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  } catch (e) {
    console.warn("SignOut error", e);
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  }
}

// Subscribe to Firebase Auth state changes for session persistence
export function subscribeAuthState(callback: (user: any | null) => void) {
  return onAuthStateChanged(auth, async (authUser) => {
    if (authUser && authUser.email) {
      const profile = await fetchUserProfileByEmail(authUser.email);
      if (profile) {
        callback(profile);
        return;
      }
    }
    
    const saved = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (saved) {
      try {
        callback(JSON.parse(saved));
        return;
      } catch (e) {
        console.warn("Failed to parse saved session", e);
      }
    }

    callback(null);
  });
}

// Upload the file only. Database metadata is handled separately during FastAPI cutover.
export async function uploadProviderDocumentFile(
  providerId: string,
  fileName: string,
  fileDataUrl: string
): Promise<ProviderDocumentItem> {
  const fileId = `doc_${Date.now().toString().slice(-6)}`;
  const nowStr = new Date().toISOString();
  
  let format = 'JPG';
  if (fileDataUrl.includes('application/pdf') || fileName.toLowerCase().endsWith('.pdf')) {
    format = 'PDF';
  } else if (fileDataUrl.includes('image/png') || fileName.toLowerCase().endsWith('.png')) {
    format = 'PNG';
  }

  let fileUrl = fileDataUrl;
  if (fileDataUrl.startsWith('data:')) {
    try {
      const storagePath = `providers/${providerId}/documents/${fileId}_${fileName.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
      const fileRef = storageRef(storage, storagePath);
      const snapshot = await uploadString(fileRef, fileDataUrl, 'data_url');
      fileUrl = await getDownloadURL(snapshot.ref);
    } catch (err) {
      console.warn("Storage document upload error fallback:", err);
    }
  }

  const newDocItem: ProviderDocumentItem = {
    fileId,
    fileName,
    fileUrl,
    format,
    uploadedAt: nowStr
  };

  return newDocItem;
}

// Upload Provider Document item to Firebase Storage and update RTDB documents node
export async function uploadProviderDocument(
  providerId: string,
  category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork',
  fileName: string,
  fileDataUrl: string
): Promise<ProviderDocumentItem> {
  const newDocItem = await uploadProviderDocumentFile(providerId, fileName, fileDataUrl);

  const provRef = ref(db, `providers/${providerId}`);
  const snapshot = await get(provRef);
  const currentProvider = snapshot.exists() ? snapshot.val() : {};

  if (currentProvider.verified || currentProvider.documents?.status === true) {
    throw new Error("Document upload is locked while verification is requested or profile is verified.");
  }

  const currentDocs = currentProvider.documents || {};
  const categoryList: ProviderDocumentItem[] = currentDocs[category] || [];

  const updatedCategoryList = [...categoryList, newDocItem];
  const updatedDocs = {
    ...currentDocs,
    [category]: updatedCategoryList
  };

  await update(provRef, { documents: updatedDocs });

  const existingStr = localStorage.getItem(LOCAL_STORAGE_PROVIDERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  if (existing[providerId]) {
    existing[providerId].documents = updatedDocs;
    localStorage.setItem(LOCAL_STORAGE_PROVIDERS_KEY, JSON.stringify(existing));
  }

  return newDocItem;
}

// Delete Provider Document item from RTDB documents node
export async function deleteProviderDocument(
  providerId: string,
  category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork',
  fileId: string
): Promise<void> {
  const provRef = ref(db, `providers/${providerId}`);
  const snapshot = await get(provRef);
  if (!snapshot.exists()) return;

  const currentProvider = snapshot.val();
  if (currentProvider.verified || currentProvider.documents?.status === true) {
    throw new Error("Document deletion is locked while verification is requested or profile is verified.");
  }

  const currentDocs = currentProvider.documents || {};
  const categoryList: ProviderDocumentItem[] = currentDocs[category] || [];

  const updatedCategoryList = categoryList.filter(item => item.fileId !== fileId);
  const updatedDocs = {
    ...currentDocs,
    [category]: updatedCategoryList
  };

  await update(provRef, { documents: updatedDocs });

  const existingStr = localStorage.getItem(LOCAL_STORAGE_PROVIDERS_KEY);
  const existing = existingStr ? JSON.parse(existingStr) : {};
  if (existing[providerId]) {
    existing[providerId].documents = updatedDocs;
    localStorage.setItem(LOCAL_STORAGE_PROVIDERS_KEY, JSON.stringify(existing));
  }
}

// Local Backup Helpers
function saveToLocalBackup(key: string, id: string, item: any) {
  try {
    const existingStr = localStorage.getItem(key);
    const existing = existingStr ? JSON.parse(existingStr) : {};
    existing[id] = item;
    localStorage.setItem(key, JSON.stringify(existing));
  } catch (e) {
    console.error("Local storage write error", e);
  }
}

function getLocalBackup<T>(key: string): T[] {
  try {
    const existingStr = localStorage.getItem(key);
    if (existingStr) {
      const parsed = JSON.parse(existingStr);
      return Object.keys(parsed).map(id => ({ id, ...parsed[id] }));
    }
  } catch (e) {
    console.error("Local storage read error", e);
  }
  return [];
}

// Daily Demand Types & Helpers
export interface DailyDemandCategoryItem {
  id?: string;
  service_category: string;
  Monday: number;
  Tuesday: number;
  Wednesday: number;
  Thursday: number;
  Friday: number;
  Saturday: number;
  Sunday: number;
  total_weekly: number;
  avg_daily: number;
  demand_level: 'HIGH' | 'MEDIUM' | 'LOW' | string;
}

export interface DailyDemandData {
  compile_date?: string;
  start_date?: string;
  end_date?: string;
  target_week?: string;
  last_updated?: string;
  by_category?: Record<string, DailyDemandCategoryItem>;
  summary?: Array<{
    "Service Category": string;
    Monday: number;
    Tuesday: number;
    Wednesday: number;
    Thursday: number;
    Friday: number;
    Saturday: number;
    Sunday: number;
    "Total Weekly Orders": number;
    "Avg Daily Orders": number;
    "Weekly Demand Level": string;
  }>;
}

export async function fetchDailyDemand(): Promise<DailyDemandData | null> {
  try {
    const demandRef = ref(db, 'daily_demand/current');
    const snapshot = await get(demandRef);
    if (snapshot.exists()) {
      return snapshot.val() as DailyDemandData;
    }

    const rootDemandRef = ref(db, 'daily_demand');
    const rootSnapshot = await get(rootDemandRef);
    if (rootSnapshot.exists()) {
      const val = rootSnapshot.val();
      if (val.current) return val.current as DailyDemandData;
      return val as DailyDemandData;
    }
  } catch (err) {
    console.warn("Failed to fetch daily_demand from Firebase RTDB, fallback to seed:", err);
  }

  if ((rtdbSeedData as any).daily_demand?.current) {
    return (rtdbSeedData as any).daily_demand.current as DailyDemandData;
  }

  return null;
}
