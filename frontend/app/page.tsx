export default async function Home() {
  const api = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const res = await fetch(`${api}/news?q=&limit=10`, { cache: "no-store" }).catch(() => null);
  let items: any[] = [];
  if (res && res.ok) items = await res.json();

  return (
    <main style={{ padding: 24 }}>
      <h1>Thandev Feed</h1>
      <p>Realtime security items (CVE/KEV/PoCs). This is a placeholder UI.</p>
      <ul>
        {items.map((i) => (
          <li key={i.id}>
            <strong>{i.title}</strong>
            {i.is_kev ? " 🔔 KEV" : ""} {i.has_exploit ? " 💣 Exploit" : ""}
          </li>
        ))}
      </ul>
    </main>
  );
}
