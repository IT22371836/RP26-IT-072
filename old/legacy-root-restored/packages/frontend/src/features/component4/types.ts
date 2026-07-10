export type TokenTag = {
  token: string;
  tag: string;
};

export type AspectScores = {
  QUAL: number | null;
  PRICE: number | null;
  TIME: number | null;
  COMM: number | null;
};

export type AnalyzeResponse = {
  status: string;
  text: string;
  tokens: TokenTag[];
  aspects: AspectScores;
  timestamp: string;
};

export type BatchResultItem = {
  text: string;
  result: AnalyzeResponse;
};

export type BatchAnalyzeResponse = {
  status: string;
  batch_size: number;
  timestamp: string;
  results: BatchResultItem[];
};
