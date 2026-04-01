// Session types
export interface Session {
  session_id: string;
  created_at: string;
  status: 'active' | 'processing' | 'completed';
  document_registry: Record<string, DocumentInfo>;
  name_history: NameHistoryEntry[];
}

export interface SessionListItem {
  session_id: string;
  name: string;
  created_at: string;
  status: 'active' | 'processing' | 'completed';
  document_count: number;
  fact_count: number;
}

export interface NameHistoryEntry {
  name: string;
  timestamp: string;
  reason: string;
  previous_name?: string;
}

// Document types
export interface DocumentInfo {
  original_pdf_path: string;
  symlink_path?: string;
  text_file?: string;
  facts_file?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  added_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface DocumentListItem {
  name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  fact_count: number;
  original_path: string;
  added_at: string;
  completed_at?: string;
  error?: string;
}

// Fact types
export interface EvidenceQuote {
  quote: string;
  source_location: string;
  relevance?: string;
}

export interface ExtractedFact {
  claim: string;
  source_doc: string;
  source_location: string;
  confidence: number;
  evidence_quotes?: EvidenceQuote[];
  evidence_quote?: string;
  fact_type?: string;
  control_family?: string;
  specificity_score?: number;
  entities?: string[];
  quantitative_values?: string[];
  process_details?: Record<string, string>;
  section_context?: string;
  related_control_ids?: string[];
  auto_generated?: boolean;
}

export interface FactsListResponse {
  facts: ExtractedFact[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FactContextResponse {
  fact: ExtractedFact;
  chunk_text: string;
  line_start: number;
  line_end: number;
  highlights: HighlightRange[];
}

export interface HighlightRange {
  start: number;
  end: number;
  quote: string;
}

// Processing types
export interface ProcessingEvent {
  type: string;
  timestamp: string;
  document?: string;
  chunk_id?: string;
  message?: string;
  progress?: number;
  data?: unknown;
}

// Query types
export interface QueryRequest {
  query: string;
  max_passes?: number;
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: SourceEvidence[];
  duration: string;
}

export interface BatchProgress {
  phase: 'selecting' | 'answering';
  total_batches: number;
  completed: number;
  running: number;
  facts_found: number;
}

export interface QueryStreamCallbacks {
  onProgress?: (progress: BatchProgress) => void;
  onStatus?: (status: { message: string; totalFacts?: number }) => void;
  onAnswerChunk?: (chunk: string) => void;
  onSources?: (sources: SourceEvidence[]) => void;
  onResult?: (result: QueryResponse) => void;
  onError?: (error: { message: string }) => void;
}

export interface SourceEvidence {
  fact_index: number;  // Canonical fact number for citation linking
  claim: string;
  quote: string;
  document: string;
  location: string;
  confidence: number;
  chunk_text?: string;
  highlights?: number[];
}

export interface QueryHistoryEntry {
  query: string;
  answer: string;
  timestamp: string;
  sources?: string[];
}

// Request types
export interface CreateSessionRequest {
  name?: string;
  document_paths?: string[];
}

export interface AddDocumentRequest {
  path: string;
  name?: string;
}

// Claude status
export interface ClaudeStatusResponse {
  available: boolean;
  mode: 'api' | 'native' | '';
  error?: string;
}

// Error type
export interface APIError {
  error: string;
  message: string;
}
