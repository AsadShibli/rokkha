import type { Metadata } from "next";
import { Suspense } from "react";

import { CitizenIncidentView } from "@/components/citizen/incident-view";

export const metadata: Metadata = { title: "Incident" };

// The id is read on the client (useParams); the page itself has no server data to wait for.
export default function IncidentPage() {
  return (
    <Suspense>
      <CitizenIncidentView />
    </Suspense>
  );
}
