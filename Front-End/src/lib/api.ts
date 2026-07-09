/**
 * iMocha AI Presentation Studio — typed API client.
 *
 * All functions call the real FastAPI backend. Function signatures are
 * stable so screens don't need changes.
 *
 * Endpoint map:
 *   uploadDeck       → POST   /api/jobs            (multipart deck + allowRestructure)
 *   getJob           → GET    /api/jobs/{jobId}
 *   getPlan          → GET    /api/jobs/{jobId}/plan
 *   approvePlan      → POST   /api/jobs/{jobId}/plan/approve
 *   getSlides        → GET    /api/jobs/{jobId}    (extracts slides field)
 *   setSlideApproval → client-side only (no backend endpoint yet)
 *   regenerateSlide  → POST   /api/jobs/{jobId}/slides/{slideId}/regenerate
 *   getResult        → GET    /api/jobs/{jobId}/result
 *   listAssets       → GET    /api/assets
 *   listHistory      → GET    /api/jobs
 */
import type {
  BrandAsset,
  SlidePlan,
  TransformJob,
  TransformedSlide,
} from '@/types';

// Base URL for the FastAPI backend. Set VITE_API_URL in Front-End/.env.local to override.
const API = (import.meta as Record<string, unknown> & { env: Record<string, string> }).env.VITE_API_URL ?? 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Job lifecycle
// ---------------------------------------------------------------------------

export async function uploadDeck(file: File, allowRestructure: boolean): Promise<{ jobId: string }> {
  const body = new FormData();
  body.append('file', file);
  body.append('allow_restructure', String(allowRestructure));
  const res = await fetch(`${API}/api/jobs`, { method: 'POST', body });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json() as Promise<{ jobId: string }>;
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

// ---------------------------------------------------------------------------
// Review screen — slides
//
// Per-slide approval (approve / flag) is client-side only: no backend endpoint
// exists yet.  approvalOverrides stores the user's choices keyed by
// "${jobId}:${slideId}" so they survive re-fetches triggered after regeneration.
// ---------------------------------------------------------------------------

const approvalOverrides = new Map<string, TransformedSlide['approval']>();

export async function getSlides(jobId: string): Promise<TransformedSlide[]> {
  const job = await getJob(jobId);
  return (job.slides ?? [])
    .map((s) => ({
      ...s,
      approval: approvalOverrides.get(`${jobId}:${s.id}`) ?? s.approval,
    }))
    .sort((a, b) => a.index - b.index);
}

export async function setSlideApproval(
  jobId: string,
  slideId: string,
  approval: TransformedSlide['approval'],
): Promise<TransformedSlide> {
  approvalOverrides.set(`${jobId}:${slideId}`, approval);
  const job = await getJob(jobId);
  const slide = job.slides?.find((s) => s.id === slideId);
  if (!slide) throw new Error('Slide not found');
  return { ...slide, approval };
}

export async function regenerateSlide(jobId: string, slideId: string): Promise<TransformedSlide> {
  // Clear the client-side approval for this slide — it's been regenerated.
  approvalOverrides.delete(`${jobId}:${slideId}`);
  const res = await fetch(`${API}/api/jobs/${jobId}/slides/${slideId}/regenerate`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`regenerateSlide failed: ${res.status}`);
  return res.json() as Promise<TransformedSlide>;
}

// ---------------------------------------------------------------------------
// Result download
// ---------------------------------------------------------------------------

export async function getResult(jobId: string): Promise<{ pptxUrl: string; pdfUrl: string }> {
  const res = await fetch(`${API}/api/jobs/${jobId}/result`);
  if (!res.ok) throw new Error(`getResult failed: ${res.status}`);
  return res.json() as Promise<{ pptxUrl: string; pdfUrl: string }>;
}

// ---------------------------------------------------------------------------
// Asset library
// ---------------------------------------------------------------------------

export async function listAssets(): Promise<BrandAsset[]> {
  const res = await fetch(`${API}/api/assets`);
  if (!res.ok) throw new Error(`listAssets failed: ${res.status}`);
  return res.json() as Promise<BrandAsset[]>;
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export async function listHistory(): Promise<TransformJob[]> {
  const res = await fetch(`${API}/api/jobs`);
  if (!res.ok) throw new Error(`listHistory failed: ${res.status}`);
  return res.json() as Promise<TransformJob[]>;
}
