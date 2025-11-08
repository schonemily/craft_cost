export default function Head() {
  const api = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  return (
    <>
      <link rel="preconnect" href={api} crossOrigin="anonymous" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
    </>
  );
}
