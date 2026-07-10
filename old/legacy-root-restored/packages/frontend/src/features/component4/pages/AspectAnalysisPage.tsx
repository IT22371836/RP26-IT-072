import { useState } from "react";
import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import type { AnalyzeResponse } from "../types";
import { analyzeReview } from "../services/aspectAnalysisService";
import { DemoReviewPicker } from "../components/DemoReviewPicker";
import { AnalysisResultCard } from "../components/AnalysisResultCard";

export function AspectAnalysisPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(reviewText: string) {
    const trimmed = reviewText.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeReview(trimmed);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  function handleDemoSelect(demoText: string) {
    setText(demoText);
    void handleAnalyze(demoText);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void handleAnalyze(text);
  }

  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.title}>Aspect Analyser</h2>
        <p style={styles.subtitle}>
          BiLSTM + CRF model — extracts Quality, Price, Time and Communication aspects from service reviews.
        </p>
      </div>

      <div style={styles.stats}>
        <StatCard label="Model Macro F1"  value="100%"  note="All 4 aspects" />
        <StatCard label="Aspect Types"    value="4"     note="QUAL · PRICE · TIME · COMM" />
        <StatCard label="Max Tokens"      value="14"    note="Per review" />
      </div>

      <SectionCard title="Try a Sample Review">
        <DemoReviewPicker selected={text} onSelect={handleDemoSelect} />
      </SectionCard>

      <SectionCard title="Analyse a Review">
        <form onSubmit={handleSubmit} style={styles.form}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type or paste a service review…  e.g. 'Excellent service but arrived late and charged too much .'"
            style={styles.textarea}
            rows={4}
          />
          <div style={styles.formFooter}>
            <span style={styles.charHint}>{text.length} characters</span>
            <button
              type="submit"
              disabled={loading || text.trim().length === 0}
              style={{
                ...styles.btn,
                opacity: loading || text.trim().length === 0 ? 0.5 : 1,
                cursor: loading || text.trim().length === 0 ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Analysing…" : "Analyse"}
            </button>
          </div>
        </form>
      </SectionCard>

      {loading && (
        <div style={styles.spinnerWrap}>
          <div style={styles.spinner} />
          <span style={styles.spinnerText}>Running BiLSTM-CRF inference…</span>
        </div>
      )}

      {error && (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && !loading && <AnalysisResultCard result={result} />}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    display: "grid",
    gap: "16px",
  },
  title: {
    margin: 0,
    color: "#0f172a",
  },
  subtitle: {
    margin: "5px 0 0",
    color: "#475569",
    fontSize: "14px",
  },
  stats: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "10px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  textarea: {
    width: "100%",
    padding: "12px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    resize: "vertical",
    fontFamily: "inherit",
    lineHeight: "1.5",
    outline: "none",
  },
  formFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  charHint: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  btn: {
    padding: "10px 24px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: "#0f766e",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 600,
    transition: "opacity 150ms ease",
  },
  spinnerWrap: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "16px",
    backgroundColor: "#f8fafc",
    borderRadius: "10px",
    border: "1px solid #e2e8f0",
  },
  spinner: {
    width: "20px",
    height: "20px",
    borderRadius: "50%",
    border: "3px solid #e2e8f0",
    borderTopColor: "#0f766e",
    animation: "spin 0.8s linear infinite",
  },
  spinnerText: {
    fontSize: "14px",
    color: "#475569",
  },
  errorBox: {
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    fontSize: "14px",
  },
};
