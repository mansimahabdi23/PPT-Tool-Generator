import { cn } from '@/lib/utils';
import type { ApprovalState, AssetStatus, JobStatus } from '@/types';

type Status = JobStatus | ApprovalState | AssetStatus | 'info';

const styles: Record<string, string> = {
  // jobs
  parsing: 'bg-badge-fill text-badge-text',
  analyzing: 'bg-badge-fill text-badge-text',
  plan_ready: 'bg-brand-orange/10 text-brand-orange-deep',
  retrieving: 'bg-badge-fill text-badge-text',
  composing: 'bg-badge-fill text-badge-text',
  validating: 'bg-badge-fill text-badge-text',
  exporting: 'bg-badge-fill text-badge-text',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  // approvals
  pending: 'bg-surface text-ink/70',
  approved: 'bg-green-100 text-green-800',
  regenerating: 'bg-brand-orange/10 text-brand-orange-deep',
  flagged: 'bg-amber-100 text-amber-800',
  // assets
  deprecated: 'bg-zinc-200 text-zinc-700',
  info: 'bg-badge-fill text-badge-text',
};

const labels: Partial<Record<string, string>> = {
  plan_ready: 'Plan ready',
};

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const label = labels[status] ?? status.replace(/_/g, ' ');
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize',
        styles[status] ?? 'bg-surface text-ink/70',
        className,
      )}
    >
      {label}
    </span>
  );
}
