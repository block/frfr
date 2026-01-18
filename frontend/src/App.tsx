import { Routes, Route, Link, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SessionPage from './pages/SessionPage';
import FactsPage from './pages/FactsPage';
import QueryPage from './pages/QueryPage';

function App() {
  const location = useLocation();

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="container">
          <h1>
            <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
              frfr
            </Link>
          </h1>
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
    </div>
  );
}

export default App;
