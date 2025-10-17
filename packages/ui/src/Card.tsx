import * as React from "react";

type AsProp<T extends keyof JSX.IntrinsicElements> = {
  as?: T;
};

type CardProps<T extends keyof JSX.IntrinsicElements = "div"> =
  AsProp<T> & Omit<React.ComponentPropsWithoutRef<T>, "as"> & {
    className?: string;
  };

export function Card<T extends keyof JSX.IntrinsicElements = "div">(
  { as, className = "", ...props }: CardProps<T>
) {
  const Tag = (as ?? "div") as unknown as keyof JSX.IntrinsicElements;
  return (
    <Tag
      className={`rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 ${className}`}
      {...(props as any)}
    />
  );
}

export function CardHeader({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`px-4 pt-4 ${className}`} {...props} />;
}

export function CardBody({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`p-4 ${className}`} {...props} />;
}

export function CardFooter({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`px-4 pb-4 ${className}`} {...props} />;
}
