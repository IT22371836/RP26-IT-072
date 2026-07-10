export type UserRole = "customer" | "provider";

export type AuthUser = {
  email: string;
  role: UserRole;
  full_name: string;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
  // Provider only
  business_name?: string;
  service_types?: string[];
  address?: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  role: UserRole;
  email: string;
  full_name: string;
};
