package api

import (
	"net/http"

	"github.com/nesposito/frfr/internal/api/handlers"
	"github.com/nesposito/frfr/internal/api/middleware"
	"github.com/nesposito/frfr/internal/config"
	"github.com/nesposito/frfr/internal/services/session"
)

// Server holds the HTTP server and all dependencies
type Server struct {
	config       *config.Config
	sessionStore *session.Store
	mux          *http.ServeMux
}

// NewServer creates a new API server
func NewServer(cfg *config.Config) *Server {
	s := &Server{
		config:       cfg,
		sessionStore: session.NewStore(cfg.SessionStorageDir),
		mux:          http.NewServeMux(),
	}

	s.registerRoutes()
	return s
}

// registerRoutes sets up all API routes
func (s *Server) registerRoutes() {
	// Create handlers
	sessionHandler := handlers.NewSessionHandler(s.sessionStore)
	documentHandler := handlers.NewDocumentHandler(s.sessionStore, s.config)
	factsHandler := handlers.NewFactsHandler(s.sessionStore)
	processingHandler := handlers.NewProcessingHandler(s.sessionStore, s.config)
	queryHandler := handlers.NewQueryHandler(s.sessionStore, s.config)

	// Sessions
	s.mux.HandleFunc("GET /api/sessions", sessionHandler.List)
	s.mux.HandleFunc("POST /api/sessions", sessionHandler.Create)
	s.mux.HandleFunc("GET /api/sessions/{id}", sessionHandler.Get)
	s.mux.HandleFunc("DELETE /api/sessions/{id}", sessionHandler.Delete)
	s.mux.HandleFunc("PUT /api/sessions/{id}", sessionHandler.Update)

	// Documents
	s.mux.HandleFunc("GET /api/sessions/{id}/documents", documentHandler.List)
	s.mux.HandleFunc("POST /api/sessions/{id}/documents", documentHandler.Add)
	s.mux.HandleFunc("POST /api/sessions/{id}/documents/{doc}/reprocess", documentHandler.Reprocess)

	// Facts
	s.mux.HandleFunc("GET /api/sessions/{id}/facts", factsHandler.List)
	s.mux.HandleFunc("GET /api/sessions/{id}/facts/{n}/context", factsHandler.GetContext)

	// Query
	s.mux.HandleFunc("POST /api/sessions/{id}/query", queryHandler.Submit)
	s.mux.HandleFunc("GET /api/sessions/{id}/query/history", queryHandler.History)

	// Processing
	s.mux.HandleFunc("POST /api/sessions/{id}/process", processingHandler.Start)
	s.mux.HandleFunc("GET /api/sessions/{id}/process/events", processingHandler.Events)

	// Health check
	s.mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})
}

// Handler returns the HTTP handler with middleware applied
func (s *Server) Handler() http.Handler {
	// Apply middleware in reverse order (last applied runs first)
	var handler http.Handler = s.mux
	handler = middleware.Logging(handler)
	handler = middleware.CORS(handler)
	return handler
}

// ListenAndServe starts the HTTP server
func (s *Server) ListenAndServe() error {
	addr := ":" + s.config.Port
	return http.ListenAndServe(addr, s.Handler())
}
