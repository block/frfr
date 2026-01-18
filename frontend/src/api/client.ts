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
  APIError,
} from './types';

const API_BASE = '/api';

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

  async getQueryHistory(sessionId: string): Promise<QueryHistoryEntry[]> {
    return this.request<QueryHistoryEntry[]>(
      'GET',
      `/sessions/${sessionId}/query/history`
    );
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
    onError?: (error: Event) => void
  ): () => void {
    const eventSource = new EventSource(
      `${API_BASE}/sessions/${sessionId}/process/events`
    );

    eventSource.onmessage = (event) => {
      try {
        const data: ProcessingEvent = JSON.parse(event.data);
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
