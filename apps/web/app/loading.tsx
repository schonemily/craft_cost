export default function Loading() {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md items-center justify-center">
      <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-white/60 border-t-transparent" aria-label="Loading" />
    </div>
  );
}
