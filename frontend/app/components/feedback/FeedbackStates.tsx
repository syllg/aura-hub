import Icon, { type IconName } from "../Icon";

export function EmptyState({
  title,
  description,
  icon = "database",
  action,
}: {
  title: string;
  description: string;
  icon?: IconName;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="state-icon"><Icon name={icon} size={24} /></span>
      <div><strong>{title}</strong><p>{description}</p></div>
      {action}
    </div>
  );
}

export function ErrorState({ title = "Data Tidak Dapat Dimuat", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <span className="state-icon"><Icon name="alert" size={24} /></span>
      <div><strong>{title}</strong><p>{message}</p></div>
      {onRetry ? <button className="button button-secondary" type="button" onClick={onRetry}><Icon name="refresh" size={17} /> Coba Lagi</button> : null}
    </div>
  );
}

export function LoadingSkeleton({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`skeleton-stack ${className}`} aria-label="Memuat data" aria-live="polite" aria-busy="true">
      {Array.from({ length: lines }, (_, index) => <span className="skeleton" key={index} />)}
    </div>
  );
}
