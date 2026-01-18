package models

// DocumentStatus represents the processing status of a document
type DocumentStatus string

const (
	DocumentStatusPending    DocumentStatus = "pending"
	DocumentStatusProcessing DocumentStatus = "processing"
	DocumentStatusCompleted  DocumentStatus = "completed"
	DocumentStatusFailed     DocumentStatus = "failed"
)

// DocumentInfo contains metadata about a document in a session
type DocumentInfo struct {
	OriginalPDFPath string         `json:"original_pdf_path"`
	SymlinkPath     string         `json:"symlink_path,omitempty"`
	TextFile        string         `json:"text_file,omitempty"`
	FactsFile       string         `json:"facts_file,omitempty"`
	Status          DocumentStatus `json:"status"`
	AddedAt         FlexibleTime   `json:"added_at"`
	CompletedAt     *FlexibleTime  `json:"completed_at,omitempty"`
	ErrorMessage    string         `json:"error_message,omitempty"`
}

// DocumentSummary contains the LLM-generated summary of a document
type DocumentSummary struct {
	DocumentType       string        `json:"document_type"`
	StructuralPattern  string        `json:"structural_pattern"`
	SectionTypes       []SectionInfo `json:"section_types"`
	MajorHeadings      []string      `json:"major_headings"`
	TableStructure     []TableInfo   `json:"table_structure,omitempty"`
	FactDensityPattern string        `json:"fact_density_pattern"`
	ExtractionGuidance string        `json:"extraction_guidance"`
	KeyEntities        []string      `json:"key_entities,omitempty"`
	Overview           string        `json:"overview,omitempty"`
}

// SectionInfo describes a section type and its extraction priority
type SectionInfo struct {
	Name               string `json:"name"`
	ExtractionPriority string `json:"extraction_priority"` // high, medium, low
	Description        string `json:"description,omitempty"`
}

// TableInfo describes a detected table structure
type TableInfo struct {
	Name        string   `json:"name"`
	Columns     []string `json:"columns"`
	Description string   `json:"description,omitempty"`
}

// ChunkInfo contains metadata about a text chunk
type ChunkInfo struct {
	ChunkID    string `json:"chunk_id"`
	Document   string `json:"document"`
	Text       string `json:"text"`
	LineStart  int    `json:"line_start"`
	LineEnd    int    `json:"line_end"`
	CharStart  int    `json:"char_start,omitempty"`
	CharEnd    int    `json:"char_end,omitempty"`
	SourcePath string `json:"source_path,omitempty"`
}

// ProcessingStats tracks extraction statistics for a document
type ProcessingStats struct {
	TotalChunks     int            `json:"total_chunks"`
	ProcessedChunks int            `json:"processed_chunks"`
	TotalFacts      int            `json:"total_facts"`
	AvgConfidence   float64        `json:"avg_confidence"`
	FactsByType     map[string]int `json:"facts_by_type,omitempty"`
}
