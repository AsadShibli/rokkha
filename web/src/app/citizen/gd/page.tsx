import type { Metadata } from "next";

import { CitizenGd } from "@/components/gd/citizen-gd";

export const metadata: Metadata = { title: "Online GD" };

export default function CitizenGdPage() {
  return <CitizenGd />;
}
