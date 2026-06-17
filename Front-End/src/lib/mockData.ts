import type { BrandAsset, SlidePlan, TransformJob, TransformedSlide } from '@/types';

const ph = (w: number, h: number, bg: string, fg: string, text: string) =>
  `https://placehold.co/${w}x${h}/${bg}/${fg}?text=${encodeURIComponent(text)}&font=poppins`;

export const mockPlan: SlidePlan[] = [
  { id: 'p1', index: 1, slideType: 'title', plannedLayout: 'Hero Title + Subtitle', assetTypes: ['template', 'logo'] },
  { id: 'p2', index: 2, slideType: 'agenda', plannedLayout: 'Numbered Agenda', assetTypes: ['icon'] },
  { id: 'p3', index: 3, slideType: 'content', plannedLayout: 'Two-column with icons', assetTypes: ['icon', 'infographic'] },
  { id: 'p4', index: 4, slideType: 'data', plannedLayout: 'Stat callout grid', assetTypes: ['chart', 'infographic'], restructureNote: 'Merged from slides 4–5' },
  { id: 'p5', index: 5, slideType: 'content', plannedLayout: 'Quote card', assetTypes: ['template'] },
  { id: 'p6', index: 6, slideType: 'data', plannedLayout: 'Bar chart with insights', assetTypes: ['chart'] },
  { id: 'p7', index: 7, slideType: 'divider', plannedLayout: 'Section divider', assetTypes: ['template'] },
  { id: 'p8', index: 8, slideType: 'closing', plannedLayout: 'Thank you / contact', assetTypes: ['logo', 'icon'] },
];

const makeSlide = (i: number, chips: string[], opts: Partial<TransformedSlide> = {}): TransformedSlide => ({
  id: `s${i}`,
  index: i,
  originalPreviewUrl: ph(640, 360, 'e5e7eb', '6b7280', `Original Slide ${i}`),
  transformedPreviewUrl: ph(640, 360, 'ff4a00', 'ffffff', `iMocha Slide ${i}`),
  contentUnchanged: true,
  changeChips: chips,
  approval: 'pending',
  ...opts,
});

export const mockSlides: TransformedSlide[] = [
  makeSlide(1, ['Brand colors applied', 'Display type added']),
  makeSlide(2, ['Layout improved', 'Icons added']),
  makeSlide(3, ['Brand colors applied', 'Icon added']),
  makeSlide(4, ['Merged content', 'Chart redesigned'], { restructureNote: 'Merged from slides 4–5' }),
  makeSlide(5, ['Typography refined']),
  makeSlide(6, ['Chart redesigned', 'Insights highlighted']),
  makeSlide(7, ['Divider styled']),
  makeSlide(8, ['Brand colors applied', 'Contact block added']),
];

export const mockHistory: TransformJob[] = [
  { id: 'job_001', deckName: 'Q3 Sales Pitch.pptx', status: 'completed', allowRestructure: true, slideCount: 12, createdAt: '2026-06-09T10:24:00Z', brandCompliancePassed: true, contentFidelity: '100% of claims preserved', processingSeconds: 48 },
  { id: 'job_002', deckName: 'Enterprise Onboarding.pptx', status: 'completed', allowRestructure: false, slideCount: 18, createdAt: '2026-06-07T14:10:00Z', brandCompliancePassed: true, contentFidelity: '100% of claims preserved', processingSeconds: 62 },
  { id: 'job_003', deckName: 'Product Roadmap H2.pptx', status: 'completed', allowRestructure: true, slideCount: 9, createdAt: '2026-06-05T09:02:00Z', brandCompliancePassed: true, contentFidelity: '100% of claims preserved', processingSeconds: 35 },
  { id: 'job_004', deckName: 'Investor Update.pptx', status: 'failed', allowRestructure: false, slideCount: 0, createdAt: '2026-06-03T16:45:00Z' },
  { id: 'job_005', deckName: 'Customer Success Stories.pptx', status: 'completed', allowRestructure: true, slideCount: 14, createdAt: '2026-05-30T11:30:00Z', brandCompliancePassed: true, contentFidelity: '100% of claims preserved', processingSeconds: 54 },
];

export const mockAssets: BrandAsset[] = [
  { id: 'a1', name: 'iMocha Cover Template', type: 'template', slot: 'cover', status: 'approved', version: 'v3.2', owner: 'Brand Team', tags: ['cover', 'hero'], thumbnailUrl: ph(240, 160, 'ff4a00', 'ffffff', 'Cover') },
  { id: 'a2', name: 'iMocha Logo (Light)', type: 'logo', slot: 'cover', status: 'approved', version: 'v2.0', owner: 'Brand Team', tags: ['logo'], thumbnailUrl: ph(240, 160, '111827', 'ff4a00', 'Logo') },
  { id: 'a3', name: 'Skill Assessment Icon Set', type: 'icon', slot: 'content', status: 'approved', version: 'v1.4', owner: 'Design', tags: ['icons', 'skills'], thumbnailUrl: ph(240, 160, 'ede9fe', '5b21b6', 'Icons') },
  { id: 'a4', name: 'Talent Funnel Infographic', type: 'infographic', slot: 'content', status: 'approved', version: 'v1.0', owner: 'Design', tags: ['funnel'], thumbnailUrl: ph(240, 160, '481aec', 'ffffff', 'Funnel') },
  { id: 'a5', name: 'ROI Chart Template', type: 'chart', slot: 'content', status: 'pending', version: 'v0.9', owner: 'Marketing', tags: ['roi', 'chart'], thumbnailUrl: ph(240, 160, '7c3aed', 'ffffff', 'Chart') },
  { id: 'a6', name: 'Section Divider — Orange', type: 'template', slot: 'divider', status: 'approved', version: 'v2.1', owner: 'Brand Team', tags: ['divider'], thumbnailUrl: ph(240, 160, 'fd5b0e', 'ffffff', 'Divider') },
  { id: 'a7', name: 'Closing Thank You', type: 'template', slot: 'closing', status: 'approved', version: 'v1.8', owner: 'Brand Team', tags: ['closing'], thumbnailUrl: ph(240, 160, '111827', 'ffffff', 'Thanks') },
  { id: 'a8', name: 'Legacy Cover (2022)', type: 'template', slot: 'cover', status: 'deprecated', version: 'v1.0', owner: 'Brand Team', expiresAt: '2024-01-01', tags: ['legacy'], thumbnailUrl: ph(240, 160, '9ca3af', 'ffffff', 'Legacy') },
];
