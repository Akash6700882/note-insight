import { useState } from "react";
import { useAuth } from "./useAuth";
import { Login } from "./components/Login";
import { NoteForm } from "./components/NoteForm";
import { History } from "./components/History";
import { NoteView } from "./components/NoteView";

export default function App() {
  const auth = useAuth();
  const [openNoteId, setOpenNoteId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  if (auth.loading) return <div className="centered muted">Loading…</div>;
  if (!auth.user) return <Login auth={auth} />;

  return (
    <div className="app">
      <header className="topbar">
        <h1>Note Insight</h1>
        <div className="row">
          <span className="muted">{auth.user.email}</span>
          <button className="link" onClick={auth.logout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="container">
        {openNoteId ? (
          <NoteView
            noteId={openNoteId}
            onBack={() => {
              setOpenNoteId(null);
              setRefreshKey((k) => k + 1);
            }}
          />
        ) : (
          <>
            <NoteForm
              onAnalyzed={(id) => {
                setRefreshKey((k) => k + 1);
                setOpenNoteId(id);
              }}
            />
            <History refreshKey={refreshKey} onOpen={setOpenNoteId} />
          </>
        )}
      </main>
    </div>
  );
}
