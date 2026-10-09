import type { Metadata } from "next";

import { AdminOfficers } from "@/components/admin/officers";

export const metadata: Metadata = { title: "Officers" };

export default function OfficersPage() {
  return <AdminOfficers />;
}
