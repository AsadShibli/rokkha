import type { Role } from "./types";

/** Seeded demo accounts (scripts/seed.py). Public on purpose: the demo is read-and-play. */
export const DEMO_PASSWORD = "rokkha1234";

export const DEMO_ACCOUNTS: { role: Role; phone: string }[] = [
  { role: "citizen", phone: "+8801733000001" },
  { role: "officer", phone: "+8801722000003" }, // Badda, on duty near Gulshan 1
  { role: "station_admin", phone: "+8801711000001" }, // Gulshan
  { role: "super_admin", phone: "+8801711000000" },
];

export const API_DOCS_URL = "https://rokkha-api.onrender.com/docs";
export const SOURCE_URL = "https://github.com/AsadShibli/rokkha";
