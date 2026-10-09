import type { Metadata } from "next";

import { CitizenReport } from "@/components/citizen/report-form";

export const metadata: Metadata = { title: "Report an issue" };

export default function ReportPage() {
  return <CitizenReport />;
}
