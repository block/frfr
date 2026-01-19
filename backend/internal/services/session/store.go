package session

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/nesposito/frfr/internal/domain/models"
)

// Store handles file-based session persistence
type Store struct {
	baseDir string
}

// NewStore creates a new session store
func NewStore(baseDir string) *Store {
	return &Store{baseDir: baseDir}
}

// sessionDirs returns the standard subdirectories for a session
func sessionDirs() []string {
	return []string{"text", "facts", "chunks", "summaries"}
}

// Create creates a new session with the given ID
func (s *Store) Create(sessionID string) (*models.Session, error) {
	sessionDir := filepath.Join(s.baseDir, sessionID)

	// Check if session already exists
	if _, err := os.Stat(sessionDir); !os.IsNotExist(err) {
		return nil, fmt.Errorf("session %s already exists", sessionID)
	}

	// Create session directory and subdirectories
	if err := os.MkdirAll(sessionDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create session directory: %w", err)
	}

	for _, subdir := range sessionDirs() {
		if err := os.MkdirAll(filepath.Join(sessionDir, subdir), 0755); err != nil {
			return nil, fmt.Errorf("failed to create %s directory: %w", subdir, err)
		}
	}

	// Create session object
	session := models.NewSession(sessionID)

	// Save metadata
	if err := s.saveMetadata(session); err != nil {
		// Clean up on failure
		os.RemoveAll(sessionDir)
		return nil, err
	}

	return session, nil
}

// Get retrieves a session by ID
func (s *Store) Get(sessionID string) (*models.Session, error) {
	metadataPath := filepath.Join(s.baseDir, sessionID, "metadata.json")

	data, err := os.ReadFile(metadataPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("session %s not found", sessionID)
		}
		return nil, fmt.Errorf("failed to read session metadata: %w", err)
	}

	var session models.Session
	if err := json.Unmarshal(data, &session); err != nil {
		return nil, fmt.Errorf("failed to parse session metadata: %w", err)
	}

	return &session, nil
}

// List returns all sessions as summary items
func (s *Store) List() ([]models.SessionListItem, error) {
	entries, err := os.ReadDir(s.baseDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []models.SessionListItem{}, nil
		}
		return nil, fmt.Errorf("failed to read sessions directory: %w", err)
	}

	// Initialize as empty slice (not nil) so JSON returns [] not null
	items := make([]models.SessionListItem, 0)
	for _, entry := range entries {
		if !entry.IsDir() || strings.HasPrefix(entry.Name(), ".") {
			continue
		}

		session, err := s.Get(entry.Name())
		if err != nil {
			continue // Skip invalid sessions
		}

		factCount, _ := s.CountFacts(entry.Name())

		items = append(items, models.SessionListItem{
			SessionID:     session.SessionID,
			Name:          session.GetName(),
			CreatedAt:     session.CreatedAt,
			Status:        session.Status,
			DocumentCount: session.GetDocumentCount(),
			FactCount:     factCount,
		})
	}

	// Sort by creation date, newest first
	sort.Slice(items, func(i, j int) bool {
		return items[i].CreatedAt.Time.After(items[j].CreatedAt.Time)
	})

	return items, nil
}

// Update saves changes to an existing session
func (s *Store) Update(session *models.Session) error {
	sessionDir := filepath.Join(s.baseDir, session.SessionID)
	if _, err := os.Stat(sessionDir); os.IsNotExist(err) {
		return fmt.Errorf("session %s not found", session.SessionID)
	}
	return s.saveMetadata(session)
}

// Delete removes a session and all its data
func (s *Store) Delete(sessionID string) error {
	sessionDir := filepath.Join(s.baseDir, sessionID)
	if _, err := os.Stat(sessionDir); os.IsNotExist(err) {
		return fmt.Errorf("session %s not found", sessionID)
	}
	return os.RemoveAll(sessionDir)
}

// Rename changes the session ID (directory name)
func (s *Store) Rename(oldID, newID, reason string) (*models.Session, error) {
	session, err := s.Get(oldID)
	if err != nil {
		return nil, err
	}

	oldDir := filepath.Join(s.baseDir, oldID)
	newDir := filepath.Join(s.baseDir, newID)

	// Check new name doesn't exist
	if _, err := os.Stat(newDir); !os.IsNotExist(err) {
		return nil, fmt.Errorf("session %s already exists", newID)
	}

	// Rename directory
	if err := os.Rename(oldDir, newDir); err != nil {
		return nil, fmt.Errorf("failed to rename session directory: %w", err)
	}

	// Update session metadata
	session.SessionID = newID
	session.AddNameHistory(newID, reason)

	// Update document paths in registry
	for name, doc := range session.DocumentRegistry {
		if doc.TextFile != "" {
			doc.TextFile = strings.Replace(doc.TextFile, oldID, newID, 1)
		}
		if doc.FactsFile != "" {
			doc.FactsFile = strings.Replace(doc.FactsFile, oldID, newID, 1)
		}
		session.DocumentRegistry[name] = doc
	}

	if err := s.saveMetadata(session); err != nil {
		// Try to revert
		os.Rename(newDir, oldDir)
		return nil, err
	}

	return session, nil
}

// saveMetadata writes session metadata to disk
func (s *Store) saveMetadata(session *models.Session) error {
	metadataPath := filepath.Join(s.baseDir, session.SessionID, "metadata.json")

	data, err := json.MarshalIndent(session, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal session metadata: %w", err)
	}

	if err := os.WriteFile(metadataPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write session metadata: %w", err)
	}

	return nil
}

// GetSessionDir returns the path to a session's directory
func (s *Store) GetSessionDir(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID)
}

// GetTextDir returns the path to a session's text directory
func (s *Store) GetTextDir(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID, "text")
}

// GetFactsDir returns the path to a session's facts directory
func (s *Store) GetFactsDir(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID, "facts")
}

// GetChunksDir returns the path to a session's chunks directory
func (s *Store) GetChunksDir(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID, "chunks")
}

// GetSummariesDir returns the path to a session's summaries directory
func (s *Store) GetSummariesDir(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID, "summaries")
}

// AddDocument adds a document to a session
func (s *Store) AddDocument(sessionID, docName, pdfPath string) error {
	session, err := s.Get(sessionID)
	if err != nil {
		return err
	}

	if session.DocumentRegistry == nil {
		session.DocumentRegistry = make(map[string]models.DocumentInfo)
	}

	session.DocumentRegistry[docName] = models.DocumentInfo{
		OriginalPDFPath: pdfPath,
		Status:          models.DocumentStatusPending,
		AddedAt:         models.FlexibleTime{Time: time.Now()},
	}

	return s.Update(session)
}

// UpdateDocumentStatus updates the status of a document
func (s *Store) UpdateDocumentStatus(sessionID, docName string, status models.DocumentStatus, errMsg string) error {
	session, err := s.Get(sessionID)
	if err != nil {
		return err
	}

	doc, ok := session.DocumentRegistry[docName]
	if !ok {
		return fmt.Errorf("document %s not found in session", docName)
	}

	doc.Status = status
	doc.ErrorMessage = errMsg // Always update (clears on success)
	if status == models.DocumentStatusCompleted {
		now := models.FlexibleTime{Time: time.Now()}
		doc.CompletedAt = &now
	}

	session.DocumentRegistry[docName] = doc
	return s.Update(session)
}

// SaveChunkFacts saves facts extracted from a chunk
func (s *Store) SaveChunkFacts(sessionID, docName, chunkID string, facts []models.ExtractedFact) error {
	factsDir := s.GetFactsDir(sessionID)
	filename := fmt.Sprintf("%s_%s.json", docName, chunkID)
	factsPath := filepath.Join(factsDir, filename)

	data, err := json.MarshalIndent(facts, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal facts: %w", err)
	}

	return os.WriteFile(factsPath, data, 0644)
}

// LoadAllFacts loads all facts for a session
func (s *Store) LoadAllFacts(sessionID string) ([]models.ExtractedFact, error) {
	factsDir := s.GetFactsDir(sessionID)

	entries, err := os.ReadDir(factsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []models.ExtractedFact{}, nil
		}
		return nil, err
	}

	var allFacts []models.ExtractedFact
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(factsDir, entry.Name()))
		if err != nil {
			continue
		}

		var facts []models.ExtractedFact
		if err := json.Unmarshal(data, &facts); err != nil {
			continue
		}

		// Extract chunk ID from filename (e.g., "DocName_chunk_0000.json" -> "chunk_0000")
		chunkID := extractChunkIDFromFilename(entry.Name())

		// Tag each fact with its chunk ID and global index
		for i := range facts {
			if facts[i].ChunkID == "" {
				facts[i].ChunkID = chunkID
			}
			facts[i].GlobalIndex = len(allFacts) + i + 1 // 1-indexed
		}

		allFacts = append(allFacts, facts...)
	}

	return allFacts, nil
}

// extractChunkIDFromFilename extracts chunk ID from a facts filename
// e.g., "DocName_chunk_0000.json" -> "chunk_0000"
func extractChunkIDFromFilename(filename string) string {
	name := strings.TrimSuffix(filename, ".json")
	if idx := strings.LastIndex(name, "_chunk_"); idx != -1 {
		return "chunk_" + name[idx+7:] // skip "_chunk_" prefix, add "chunk_" back
	}
	return ""
}

// LoadDocumentFacts loads facts for a specific document
func (s *Store) LoadDocumentFacts(sessionID, docName string) ([]models.ExtractedFact, error) {
	factsDir := s.GetFactsDir(sessionID)

	entries, err := os.ReadDir(factsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []models.ExtractedFact{}, nil
		}
		return nil, err
	}

	var docFacts []models.ExtractedFact
	prefix := docName + "_"
	for _, entry := range entries {
		if !strings.HasPrefix(entry.Name(), prefix) || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(factsDir, entry.Name()))
		if err != nil {
			continue
		}

		var facts []models.ExtractedFact
		if err := json.Unmarshal(data, &facts); err != nil {
			continue
		}

		docFacts = append(docFacts, facts...)
	}

	return docFacts, nil
}

// CountFacts returns the total number of facts in a session
func (s *Store) CountFacts(sessionID string) (int, error) {
	facts, err := s.LoadAllFacts(sessionID)
	if err != nil {
		return 0, err
	}
	return len(facts), nil
}

// GetProcessedChunks returns chunk IDs that have been processed for a document
func (s *Store) GetProcessedChunks(sessionID, docName string) ([]string, error) {
	factsDir := s.GetFactsDir(sessionID)

	entries, err := os.ReadDir(factsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	var chunks []string
	prefix := docName + "_"
	suffix := ".json"
	for _, entry := range entries {
		name := entry.Name()
		if strings.HasPrefix(name, prefix) && strings.HasSuffix(name, suffix) {
			chunkID := strings.TrimSuffix(strings.TrimPrefix(name, prefix), suffix)
			chunks = append(chunks, chunkID)
		}
	}

	return chunks, nil
}

// SaveChunkText saves a chunk's text content
func (s *Store) SaveChunkText(sessionID, docName, chunkID, text string) error {
	chunksDir := s.GetChunksDir(sessionID)
	filename := fmt.Sprintf("%s_%s.txt", docName, chunkID)
	return os.WriteFile(filepath.Join(chunksDir, filename), []byte(text), 0644)
}

// LoadChunkText loads a chunk's text content
func (s *Store) LoadChunkText(sessionID, docName, chunkID string) (string, error) {
	chunksDir := s.GetChunksDir(sessionID)
	filename := fmt.Sprintf("%s_%s.txt", docName, chunkID)
	data, err := os.ReadFile(filepath.Join(chunksDir, filename))
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// SaveDocumentSummary saves a document summary
func (s *Store) SaveDocumentSummary(sessionID, docName string, summary *models.DocumentSummary) error {
	summariesDir := s.GetSummariesDir(sessionID)
	filename := fmt.Sprintf("%s.json", docName)
	data, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(summariesDir, filename), data, 0644)
}

// LoadDocumentSummary loads a document summary
func (s *Store) LoadDocumentSummary(sessionID, docName string) (*models.DocumentSummary, error) {
	summariesDir := s.GetSummariesDir(sessionID)
	filename := fmt.Sprintf("%s.json", docName)
	data, err := os.ReadFile(filepath.Join(summariesDir, filename))
	if err != nil {
		return nil, err
	}

	var summary models.DocumentSummary
	if err := json.Unmarshal(data, &summary); err != nil {
		return nil, err
	}
	return &summary, nil
}

// SaveDocumentText saves extracted text for a document
func (s *Store) SaveDocumentText(sessionID, docName, text string) error {
	textDir := s.GetTextDir(sessionID)
	filename := fmt.Sprintf("%s.txt", docName)
	return os.WriteFile(filepath.Join(textDir, filename), []byte(text), 0644)
}

// LoadDocumentText loads extracted text for a document
func (s *Store) LoadDocumentText(sessionID, docName string) (string, error) {
	textDir := s.GetTextDir(sessionID)
	filename := fmt.Sprintf("%s.txt", docName)
	data, err := os.ReadFile(filepath.Join(textDir, filename))
	if err != nil {
		return "", err
	}
	return string(data), nil
}
