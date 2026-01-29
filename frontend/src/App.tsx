import { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SessionPage from './pages/SessionPage';
import FactsPage from './pages/FactsPage';
import QueryPage from './pages/QueryPage';
import ClaudeStatusModal from './components/common/ClaudeStatusModal';
import SettingsModal from './components/common/SettingsModal';
import { api } from './api/client';

function SettingsIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function App() {
  const location = useLocation();
  const [showClaudeModal, setShowClaudeModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  useEffect(() => {
    api.checkClaudeStatus().then((status) => {
      if (!status.available) {
        setShowClaudeModal(true);
      }
    }).catch((err) => {
      console.error('Failed to check Claude status:', err);
    });
  }, []);

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="container">
          <h1>
            <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
              frfr
            </Link>
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <nav>
              <Link
                to="/"
                style={{
                  fontWeight: location.pathname === '/' ? 600 : 400,
                }}
              >
                Sessions
              </Link>
            </nav>
            <button
              onClick={() => setShowSettingsModal(true)}
              style={{
                background: 'none',
                border: 'none',
                padding: '0.375rem',
                borderRadius: '0.375rem',
                color: 'var(--color-text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-bg)';
                e.currentTarget.style.color = 'var(--color-text)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = 'var(--color-text-muted)';
              }}
              title="Settings"
            >
              <SettingsIcon />
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">
        <div className="container">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/sessions/:sessionId" element={<SessionPage />} />
            <Route path="/sessions/:sessionId/facts" element={<FactsPage />} />
            <Route path="/sessions/:sessionId/query" element={<QueryPage />} />
          </Routes>
        </div>
      </main>
      {showClaudeModal && (
        <ClaudeStatusModal onClose={() => setShowClaudeModal(false)} />
      )}
      {showSettingsModal && (
        <SettingsModal onClose={() => setShowSettingsModal(false)} />
      )}
    </div>
  );
}

export default App;
