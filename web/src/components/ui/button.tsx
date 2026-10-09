import Link from "next/link";

import { cn } from "@/lib/utils";

const variants = {
  primary: "bg-ink text-white hover:bg-ink-soft",
  accent: "bg-accent text-ink hover:brightness-95",
  outline: "border border-line bg-white text-ink hover:border-ink/30",
  ghost: "text-ink hover:bg-ink/5",
  sos: "bg-sos text-white hover:bg-sos-strong",
} as const;

const sizes = {
  sm: "h-9 px-3.5 text-sm",
  md: "h-11 px-5 text-[15px]",
  lg: "h-13 px-6 text-base",
} as const;

type Variant = keyof typeof variants;
type Size = keyof typeof sizes;

function classes(variant: Variant, size: Size, className?: string) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition",
    "disabled:pointer-events-none disabled:opacity-60",
    variants[variant],
    sizes[size],
    className,
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export function Button({ variant = "primary", size = "md", className, ...props }: ButtonProps) {
  return <button className={classes(variant, size, className)} {...props} />;
}

type ButtonLinkProps = React.ComponentProps<typeof Link> & { variant?: Variant; size?: Size };

export function ButtonLink({ variant = "primary", size = "md", className, ...props }: ButtonLinkProps) {
  return <Link className={classes(variant, size, className)} {...props} />;
}
