import { Chat } from "@/components/Chat";

export default function Home() {
  return (
    <main className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            🌷
          </span>
          <span className="brand-name">Lily</span>
        </div>
        <span className="brand-tag">Refrigerator &amp; dishwasher parts</span>
      </header>
      <Chat />
    </main>
  );
}
