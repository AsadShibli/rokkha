export type Role = "citizen" | "officer" | "station_admin" | "super_admin";

export type User = {
  id: number;
  name: string;
  phone: string;
  email: string | null;
  role: Role;
  is_active: boolean;
  station_id: number | null;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

/** The API's single error shape. */
export type ApiErrorBody = {
  error: { code: string; message: string; details: { field: string; message: string }[] };
};
