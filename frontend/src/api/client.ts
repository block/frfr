import type {
  Session,
  SessionListItem,
  DocumentListItem,
  FactsListResponse,
  FactContextResponse,
  QueryRequest,
  QueryResponse,
  QueryHistoryEntry,
  ProcessingEvent,
  CreateSessionRequest,
  AddDocumentRequest,
  AddSlackChannelRequest,
  APIError,
  BatchProgress,
  QueryStreamCallbacks,
  ClaudeStatusResponse,
  SourceEvidence,
} from './types';
import '../types/electron.d.ts';

// Determine API base URL
// In Electron: get port from URL query param (set by main process)
// In browser: use relative path (proxied by Vite)
function getApiBase(): string {
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const backendPort = params.get('backendPort');
    if (backendPort) {
      return `http://127.0.0.1:${backendPort}/api`;
    }
  }
  return '/api';
}

const API_BASE = getApiBase();

class APIClient {
  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${path}`, options);

    if (!response.ok) {
      const error: APIError = await response.json().catch(() => ({
        error: 'Unknown error',
        message: response.statusText,
      }));
      throw new Error(error.message || error.error);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // Sessions
  async listSessions(): Promise<SessionListItem[]> {
    return this.request<SessionListItem[]>('GET', '/sessions');
  }

  async createSession(req: CreateSessionRequest): Promise<Session> {
    return this.request<Session>('POST', '/sessions', req);
  }

  async getSession(id: string): Promise<Session> {
    return this.request<Session>('GET', `/sessions/${id}`);
  }

  async deleteSession(id: string): Promise<void> {
    return this.request<void>('DELETE', `/sessions/${id}`);
  }

  async updateSession(
    id: string,
    update: { name?: string; status?: string }
  ): Promise<Session> {
    return this.request<Session>('PUT', `/sessions/${id}`, update);
  }

  // Documents
  async listDocuments(sessionId: string): Promise<DocumentListItem[]> {
    return this.request<DocumentListItem[]>(
      'GET',
      `/sessions/${sessionId}/documents`
    );
  }

  async addDocument(
    sessionId: string,
    req: AddDocumentRequest
  ): Promise<DocumentListItem> {
    return this.request<DocumentListItem>(
      'POST',
      `/sessions/${sessionId}/documents`,
      req
    );
  }

  async addSlackChannel(
    sessionId: string,
    req: AddSlackChannelRequest
  ): Promise<DocumentListItem> {
    return this.request<DocumentListItem>(
      'POST',
      `/sessions/${sessionId}/slack`,
      req
    );
  }

  async reprocessDocument(
    sessionId: string,
    docName: string
  ): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>(
      'POST',
      `/sessions/${sessionId}/documents/${encodeURIComponent(docName)}/reprocess`
    );
  }

  // Facts
  async listFacts(
    sessionId: string,
    params?: {
      search?: string;
      type?: string;
      document?: string;
      min_confidence?: number;
      page?: number;
      page_size?: number;
    }
  ): Promise<FactsListResponse> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    const path = `/sessions/${sessionId}/facts${query ? `?${query}` : ''}`;
    return this.request<FactsListResponse>('GET', path);
  }

  async getFactContext(
    sessionId: string,
    factIndex: number
  ): Promise<FactContextResponse> {
    return this.request<FactContextResponse>(
      'GET',
      `/sessions/${sessionId}/facts/${factIndex}/context`
    );
  }

  // Query
  async submitQuery(sessionId: string, req: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>(
      'POST',
      `/sessions/${sessionId}/query`,
      req
    );
  }

  // Streaming query with progress updates (falls back to non-streaming if needed)
  submitQueryStream(
    sessionId: string,
    req: QueryRequest,
    callbacks: QueryStreamCallbacks
  ): () => void {
    const controller = new AbortController();

    // Use fetch with POST for SSE (EventSource only supports GET)
    fetch(`${API_BASE}/sessions/${sessionId}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(req),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const error = await response.json().catch(() => ({
            message: response.statusText,
          }));
          callbacks.onError?.({ message: error.message || 'Query failed' });
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          // Fall back to non-streaming endpoint
          console.warn('Streaming not supported, falling back to regular query');
          this.submitQuery(sessionId, req)
            .then((result) => callbacks.onResult?.(result))
            .catch((err) => callbacks.onError?.({ message: err.message }));
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let eventType = ''; // Track event type across chunks

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7);
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                switch (eventType) {
                  case 'progress':
                    callbacks.onProgress?.(parsed as BatchProgress);
                    break;
                  case 'status':
                    callbacks.onStatus?.(parsed);
                    break;
                  case 'answer_chunk':
                    callbacks.onAnswerChunk?.(parsed.text);
                    break;
                  case 'sources':
                    callbacks.onSources?.(parsed as SourceEvidence[]);
                    break;
                  case 'result':
                    callbacks.onResult?.(parsed as QueryResponse);
                    break;
                  case 'error':
                    callbacks.onError?.(parsed);
                    break;
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          // Fall back to non-streaming on any error
          console.warn('Stream error, falling back to regular query:', error);
          this.submitQuery(sessionId, req)
            .then((result) => callbacks.onResult?.(result))
            .catch((err) => callbacks.onError?.({ message: err.message }));
        }
      });

    // Return abort function
    return () => controller.abort();
  }

  async getQueryHistory(sessionId: string): Promise<QueryHistoryEntry[]> {
    return this.request<QueryHistoryEntry[]>(
      'GET',
      `/sessions/${sessionId}/query/history`
    );
  }

  // File picker - uses Electron dialog when available, falls back to server
  async pickFiles(): Promise<string[]> {
    // Use Electron's native dialog if available
    if (typeof window !== 'undefined' && window.electronAPI?.pickFiles) {
      return window.electronAPI.pickFiles();
    }
    // Fall back to server-side picker (AppleScript)
    const response = await this.request<{ files: string[] }>('POST', '/files/pick');
    return response.files;
  }

  // Claude status
  async checkClaudeStatus(): Promise<ClaudeStatusResponse> {
    return this.request<ClaudeStatusResponse>('GET', '/claude/status');
  }

  // Processing
  async startProcessing(
    sessionId: string,
    documents?: string[],
    force?: boolean
  ): Promise<{ status: string; message: string; documents: string[] }> {
    return this.request<{ status: string; message: string; documents: string[] }>(
      'POST',
      `/sessions/${sessionId}/process`,
      { documents, force }
    );
  }

  subscribeToProcessingEvents(
    sessionId: string,
    onEvent: (event: ProcessingEvent) => void,
    onError?: (error: Event) => void,
    onConnected?: () => void
  ): () => void {
    const eventSource = new EventSource(
      `${API_BASE}/sessions/${sessionId}/process/events`
    );

    eventSource.onmessage = (event) => {
      try {
        const data: ProcessingEvent = JSON.parse(event.data);

        // Notify when connected
        if (data.type === 'connected' && onConnected) {
          onConnected();
        }

        onEvent(data);

        // Close on completion
        if (data.type === 'complete') {
          eventSource.close();
        }
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    };

    eventSource.onerror = (error) => {
      if (onError) {
        onError(error);
      }
      eventSource.close();
    };

    // Return cleanup function
    return () => eventSource.close();
  }
}

export const api = new APIClient();
