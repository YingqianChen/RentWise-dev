import Link from "next/link";
import { cn } from "@/lib/utils";

type Variant = "icon" | "wordmark";

interface LogoProps {
  variant?: Variant;
  eyebrow?: string;
  tagline?: string;
  size?: number;
  href?: string;
  className?: string;
}

export function Logo({
  variant = "icon",
  eyebrow,
  tagline,
  size = 40,
  href,
  className,
}: LogoProps) {
  if (variant === "wordmark") {
    const img = (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src="/logo-with-text.svg"
        alt="RentWise"
        className={cn("h-auto w-44", className)}
      />
    );
    return href ? (
      <Link href={href} aria-label="RentWise home" className="inline-flex">
        {img}
      </Link>
    ) : (
      img
    );
  }

  const inner = (
    <div className={cn("flex items-center gap-3", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo.svg"
        alt="RentWise"
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
      {(eyebrow || tagline) && (
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
              {eyebrow}
            </p>
          )}
          {tagline && (
            <p className="truncate text-xs text-gray-500">{tagline}</p>
          )}
        </div>
      )}
    </div>
  );

  return href ? (
    <Link href={href} aria-label="RentWise home" className="inline-flex">
      {inner}
    </Link>
  ) : (
    inner
  );
}
