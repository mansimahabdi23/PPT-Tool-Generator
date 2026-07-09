/**
 * iMocha AI Presentation Studio — typed API client.
 *
 * Currently returns mocked data. Replace internals with fetch calls to the
 * Python/FastAPI backend. Function signatures must remain stable so screens
 * don't need changes.
 *
 * Endpoint map:
 *   uploadDeck       → POST   /api/jobs            (multipart deck + allowRestructure)
 *   getJob           → GET    /api/jobs/{jobId}
 *   getPlan          → GET    /api/jobs/{jobId}/plan
 *   approvePlan      → POST   /api/jobs/{jobId}/plan/approve
 *   regenerateSlide  → POST   /api/jobs/{jobId}/slides/{slideId}/regenerate
 *   getResult        → GET    /api/jobs/{jobId}/result   (returns download URLs)
 *   listAssets       → GET    /api/assets
 *   createAsset      → POST   /api/assets
 *   updateAsset      → PATCH  /api/assets/{id}
 */
import type {
  BrandAsset,
  JobStatus,
  SlidePlan,
  TransformJob,
  TransformedSlide,
} from '@/types';
import { mockAssets, mockHistory, mockPlan, mockSlides } from './mockData';

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// Base URL for the FastAPI backend. Set VITE_API_URL in Front-End/.env.local to override.
const API = (import.meta as Record<string, unknown> & { env: Record<string, string> }).env.VITE_API_URL ?? 'http://localhost:8000';

// In-memory mock job store (preserves across navigations within a session).
type JobRecord = TransformJob & { _startedAt: number; _planApprovedAt?: number };
const jobs = new Map<string, JobRecord>();

const STAGE_ORDER: JobStatus[] = [
  'parsing',
  'analyzing',
  'plan_ready',
  'retrieving',
  'composing',
  'validating',
  'exporting',
  'completed',
];

const STAGE_MS = 1400;

function computeStatus(rec: JobRecord): JobStatus {
  const elapsed = Date.now() - rec._startedAt;
  const preApproveStages = STAGE_ORDER.indexOf('plan_ready'); // 2
  const preApproveTime = preApproveStages * STAGE_MS;

  if (elapsed < STAGE_MS) return 'parsing';
  if (elapsed < preApproveTime) return 'analyzing';

  // Wait at plan_ready until approval.
  if (!rec._planApprovedAt) return 'plan_ready';

  const sinceApproval = Date.now() - rec._planApprovedAt;
  const postStages = STAGE_ORDER.slice(STAGE_ORDER.indexOf('plan_ready') + 1);
  const idx = Math.min(postStages.length - 1, Math.floor(sinceApproval / STAGE_MS));
  return postStages[idx];
}

export async function uploadDeck(file: File, allowRestructure: boolean): Promise<{ jobId: string }> {
  const body = new FormData();
  body.append('file', file);
  body.append('allow_restructure', String(allowRestructure));
  const res = await fetch(`${API}/api/jobs`, { method: 'POST', body });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  const data = await res.json() as { jobId: string };
  return { jobId: data.jobId };
}

export async function getJob(jobId: string): Promise<TransformJob> {
  const res = await fetch(`${API}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error(`getJob failed: ${res.status}`);
  return res.json() as Promise<TransformJob>;
}

export async function getPlan(jobId: string): Promise<SlidePlan[]> {
  const res = await fetch(`${API}/api/jobs/${jobId}/plan`);
  if (!res.ok) throw new Error(`getPlan failed: ${res.status}`);
  return res.json() as Promise<SlidePlan[]>;
}

export async function approvePlan(jobId: string): Promise<void> {
  const res = await fetch(`${API}/api/jobs/${jobId}/plan/approve`, { method: 'POST' });
  if (!res.ok) throw new Error(`approvePlan failed: ${res.status}`);
}

// Per-slide approval state lives client-side; keep it in memory keyed by job.
const slideStates = new Map<string, Map<string, TransformedSlide>>();

function ensureSlides(jobId: string): Map<string, TransformedSlide> {
  let m = slideStates.get(jobId);
  if (!m) {
    m = new Map();
    const rec = jobs.get(jobId);
    mockSlides.forEach((s) => {
      m!.set(s.id, {
        ...s,
        restructureNote: rec?.allowRestructure ? s.restructureNote : undefined,
      });
    });
    slideStates.set(jobId, m);
  }
  return m;
}

export async function getSlides(jobId: string): Promise<TransformedSlide[]> {
  await delay(200);
  const m = ensureSlides(jobId);
  return Array.from(m.values()).sort((a, b) => a.index - b.index);
}

export async function setSlideApproval(
  jobId: string,
  slideId: string,
  approval: TransformedSlide['approval'],
): Promise<TransformedSlide> {
  await delay(150);
  const m = ensureSlides(jobId);
  const s = m.get(slideId);
  if (!s) throw new Error('Slide not found');
  const next = { ...s, approval };
  m.set(slideId, next);
  return next;
}

export async function regenerateSlide(jobId: string, slideId: string): Promise<TransformedSlide> {
  const m = ensureSlides(jobId);
  const s = m.get(slideId);
  if (!s) throw new Error('Slide not found');
  m.set(slideId, { ...s, approval: 'regenerating' });
  await delay(1400);
  const palette = ['fd5b0e', '481aec', '7c3aed', '6366f1', 'ff4a00'];
  const bg = palette[(s.retryCount ?? 0) % palette.length];
  const next: TransformedSlide = {
    ...s,
    transformedPreviewUrl: `https://placehold.co/640x360/${bg}/ffffff?text=${encodeURIComponent('iMocha Slide ' + s.index + ' v' + ((s.retryCount ?? 1) + 1))}&font=poppins`,
    approval: 'pending',
    retryCount: (s.retryCount ?? 1) + 1,
    changeChips: [...new Set([...s.changeChips, 'Regenerated'])],
  };
  m.set(slideId, next);
  return next;
}

export async function getResult(jobId: string): Promise<{ pptxUrl: string; pdfUrl: string }> {
  const res = await fetch(`${API}/api/jobs/${jobId}/result`);
  if (!res.ok) throw new Error(`getResult failed: ${res.status}`);
  const data = await res.json() as { pptxUrl: string; pdfUrl: string };
  return data;
}

export async function listAssets(): Promise<BrandAsset[]> {
  await delay(250);
  return mockAssets;
}

export async function listHistory(): Promise<TransformJob[]> {
  await delay(250);
  return mockHistory;
}
