import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <AuthLayout>
      {/* The form reads ?demo= and ?next=, so it renders on the client after the static shell. */}
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthLayout>
  );
}
