import type { Metadata } from "next";

import { AdminStations } from "@/components/admin/stations";

export const metadata: Metadata = { title: "Stations" };

export default function StationsPage() {
  return <AdminStations />;
}
