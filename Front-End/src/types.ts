export type JobStatus =
  | 'parsing'
  | 'analyzing'
  | 'plan_ready'
  | 'retrieving'
  | 'composing'
  | 'validating'
  | 'exporting'
  | 'completed'
  | 'failed';

export type SlideType = 'title' | 'agenda' | 'content' | 'data' | 'divider' | 'closing';
export type ApprovalState = 'pending' | 'approved' | 'regenerating' | 'flagged';
export type AssetType = 'template' | 'icon' | 'infographic' | 'logo' | 'chart';
export type AssetStatus = 'approved' | 'pending' | 'deprecated';

export interface SlidePlan {
  id: string;
  index: number;
  slideType: SlideType;
  plannedLayout: string;
  assetTypes: AssetType[];
  restructureNote?: string;
}

export interface TransformedSlide {
  id: string;
  index: number;
  originalPreviewUrl: string;
  transformedPreviewUrl: string;
  contentUnchanged: boolean;
  restructureNote?: string;
  changeChips: string[];
  approval: ApprovalState;
  retryCount?: number;
}

export interface TransformJob {
  id: string;
  deckName: string;
  status: JobStatus;
  allowRestructure: boolean;
  slideCount: number;
  createdAt: string;
  plan?: SlidePlan[];
  slides?: TransformedSlide[];
  brandCompliancePassed?: boolean;
  contentFidelity?: string;
  processingSeconds?: number;
}

export interface BrandAsset {
  id: string;
  name: string;
  type: AssetType;
  slot: 'cover' | 'content' | 'divider' | 'closing';
  status: AssetStatus;
  version: string;
  owner: string;
  expiresAt?: string;
  tags: string[];
  thumbnailUrl: string;
}
