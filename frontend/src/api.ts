import { errorKey } from './i18n';

export class ApiError extends Error {
  constructor(public code: string) {
    super(errorKey(code));
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init.headers,
    },
  }).catch(() => {
    throw new ApiError('NETWORK_ERROR');
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.error?.code ?? 'REQUEST_FAILED');
  }
  if (response.status === 204) return undefined as T;
  return response.json().catch(() => {
    throw new ApiError('REQUEST_FAILED');
  });
}

export type Notebook = {
  id: string;
  title: string;
  description: string;
  updated_at: string;
  source_count?: number;
  knowledge_count?: number;
  deck_count?: number;
};
export type ModelRole = 'language' | 'embedding' | 'image';
export type ModelConfig = {
  base_url: string;
  model_id: string;
  max_context_tokens: number;
  has_api_key: boolean;
  capabilities: Record<string, string | number | boolean>;
};
export type ModelSettings = {
  setup_complete: boolean;
  models: Partial<Record<ModelRole, ModelConfig>>;
};

export type ModelConcurrencySettings = {
  concurrency: number;
  min_concurrency: number;
  max_concurrency: number;
};

export type Job = {
  id: string;
  type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  stage: string;
  progress: number;
  error_code?: string;
  error_message?: string;
};
export type Source = {
  updated_at?: string;
  metadata?: {
    warnings?: string[];
    url?: string;
    final_url?: string;
    fetched_at?: string;
    image_failures?: number;
    save_images?: boolean;
    web_images_status?: string;
    web_image_limit_skipped?: number;
    images?: { id: string; status: string; image_url: string }[];
    toc?: { href: string; fragment: string; title?: string; depth?: number }[];
  };
  parser_version?: string;
  id: string;
  type: string;
  title: string;
  status: string;
  original_filename: string;
  enabled: boolean;
  job?: Job;
  error_code?: string;
  error_message?: string;
};
export type SourceNode = {
  id: string;
  source_id: string;
  title: string;
  type: string;
  parent_id?: string;
  depth: number;
  ordinal: number;
  start_page?: number;
  metadata?: { href?: string; element_id?: string };
};
export type ContentBlock = {
  id: string;
  source_id: string;
  node_id: string;
  type: string;
  text: string;
  ordinal: number;
  page_start?: number;
  location: Record<string, unknown>;
};

export type ReadingBlock = {
  type: string;
  page_start?: number;
  parts: { block_id: string; text: string }[];
  image?: {
    image_url?: string;
    original_image_url?: string;
    alt?: string;
    extraction: string;
    recognition_status: string;
    uncertain: boolean;
    error_code?: string;
  };
};

export type Scope = {
  kind: 'selected' | 'source' | 'node' | 'nodes';
  source_id?: string;
  source_ids?: string[];
  node_id?: string;
  node_ids?: string[];
};
export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Record<string, string>;
  metadata?: { answer_status?: 'insufficient_evidence'; language?: string | null };
  job?: Job;
};
export type CitationPassage = {
  image_url?: string;
  extraction?: string;
  source_id: string;
  source_title?: string;
  node_title?: string;
  page?: number;
  anchor_block_id: string;
  available: boolean;
  text?: string;
};
export type Citation = {
  passages?: CitationPassage[];
  id: string;
  available: boolean;
  message?: string;
  spans: {
    image_url?: string;
    extraction?: string;
    source_id: string;
    block_id: string;
    source_title?: string;
    node_title?: string;
    page?: number;
    quote?: string;
    available: boolean;
  }[];
};

export type KnowledgePage = {
  id: string;
  notebook_id: string;
  title: string;
  content_markdown: string;
  revision: number;
  citations: Record<string, string>;
  generation_metadata: {
    source_ids?: string[];
    block_ids?: string[];
    segment_count?: number;
    language?: string | null;
    title_pending?: boolean;
  };
  job?: Job;
  updated_at: string;
};

export type DeckScope = Omit<Scope, 'kind'> & {
  kind: Scope['kind'] | 'knowledge';
  knowledge_page_id?: string;
};
export type DeckSummary = {
  download_available?: boolean;
  batch_label?: string;
  job_status?: Job['status'];
  slide_count: number;
  id: string;
  title: string;
  status: string;
  target_slide_count: number;
  updated_at: string;
};
export type ContentBasis = 'source' | 'interpretation' | 'background' | 'analogy';
export type SlideElement = {
  id: string;
  type: string;
  text: string;
  label: string;
  citations: string[];
  basis?: ContentBasis;
  items: { label: string; text: string; citations: string[]; basis?: ContentBasis | null }[];
};
export type Slide = {
  render_current: boolean;
  assets: {
    id: string;
    request_id: string;
    status: string;
    error_code?: string;
    error_message?: string;
  }[];
  render?: { id: string; image_url: string; thumbnail_url: string; width: number; height: number };
  id: string;
  ordinal: number;
  status: string;
  revision: number;
  error_code?: string;
  error_message?: string;
  plan: { title: string; role: string; purpose: string; key_message: string };
  spec?: {
    key_message: string;
    content_elements: SlideElement[];
    asset_requests: { id: string; purpose: string }[];
  };
  citations: Record<string, string>;
};
export type Deck = DeckSummary & {
  title_mode?: 'auto' | 'source' | 'custom';
  render_mode?: 'generated_page' | 'native';
  art_direction?: {
    version: string;
    pages: Record<
      string,
      {
        index: number;
        form: string;
        surface: string;
        viewpoint: string;
        text_placement: string;
      }
    >;
    metrics: { forms: Record<string, number>; viewpoints: Record<string, number> };
  };
  pdf_export?: {
    id: string;
    status: string;
    page_count: number;
    file_size: number;
    filename?: string;
    download_url?: string;
    preview_url?: string;
    error_code?: string;
    error_message?: string;
  };
  slides: Slide[];
  job?: Job;
  revision: number;
  plan?: { narrative: string };
  style?: { concept: string; palette: Record<string, string> };
};

export type DeckSources = {
  historical: boolean;
  knowledge: { id: string; title: string; revision: number; available: boolean }[];
  sources: {
    id: string;
    title: string | null;
    type: string | null;
    selection: 'whole' | 'chapters' | 'citations';
    first_block_id: string | null;
    available: boolean;
    whole_work_background: boolean;
    chapters: {
      id: string;
      title: string;
      number?: string | null;
      path: string[];
      first_block_id: string | null;
      available: boolean;
    }[];
  }[];
};
