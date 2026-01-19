import type { DocumentListItem } from '../../api/types';

interface Props {
  documents: DocumentListItem[];
  sessionId: string;
  onReprocess: (docName: string) => void;
}

function DocumentsTable({ documents, onReprocess }: Props) {
  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      pending: 'badge badge-info',
      processing: 'badge badge-warning',
      completed: 'badge badge-success',
      failed: 'badge badge-error',
    };
    return <span className={classes[status] || 'badge'}>{status}</span>;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Document</th>
          <th>Facts</th>
          <th>Status</th>
          <th>Added</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.name}>
            <td>
              <div>
                <span style={{ fontWeight: 500 }}>{doc.name}</span>
                <p className="text-xs text-muted" style={{ marginTop: '0.25rem' }}>
                  {doc.original_path}
                </p>
              </div>
            </td>
            <td>{doc.fact_count}</td>
            <td>
              {getStatusBadge(doc.status)}
              {doc.error && (
                <p className="text-xs" style={{ color: 'var(--color-error)', marginTop: '0.25rem' }}>
                  {doc.error}
                </p>
              )}
            </td>
            <td className="text-muted text-sm">{formatDate(doc.added_at)}</td>
            <td>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => onReprocess(doc.name)}
              >
                {doc.status === 'pending' ? 'Process' : doc.status === 'processing' ? 'Restart' : 'Reprocess'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default DocumentsTable;
