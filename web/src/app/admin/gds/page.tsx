import type { Metadata } from "next";

import { GdReview } from "@/components/gd/gd-review";

export const metadata: Metadata = { title: "GD review" };

export default function GdReviewPage() {
  return <GdReview />;
}
