const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default async function Home() {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  const health = await res.json();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#10141A] text-[#E6EAF0]">
      <h1 className="text-3xl font-semibold">AEC Blueprint Intelligence System</h1>
      <p>Backend status: <span className="text-[#34C77B]">{health.status}</span></p>
    </main>
  );
}