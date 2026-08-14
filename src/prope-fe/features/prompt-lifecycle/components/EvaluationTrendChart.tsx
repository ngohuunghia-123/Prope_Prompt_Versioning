import type { EvalTrend } from '@/features/prompt-lifecycle/types';

interface EvaluationTrendChartProps { trends: EvalTrend[]; }

export function EvaluationTrendChart({ trends }: EvaluationTrendChartProps) {
  const points = trends.find((trend) => trend.metric === 'overall')?.points ?? [];
  if (!points.length) return null;
  const scores = points.map((point) => point.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const height = 200;
  const width = 100;
  const range = Math.max(0.01, max - min);
  const getX = (index: number) => (index / Math.max(1, points.length - 1)) * width;
  const getY = (score: number) => height - ((score - min + 0.02) / (range + 0.04)) * height;
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${getX(index)} ${getY(point.score)}`).join(' ');
  return (
    <div className="relative h-64"><svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" preserveAspectRatio="none"><path d={path} fill="none" stroke="var(--color-primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />{points.map((point, index) => <circle key={point.date} cx={getX(index)} cy={getY(point.score)} r="2" fill="var(--color-primary)" />)}</svg><div className="absolute bottom-0 left-0 right-0 flex justify-between text-caption text-muted"><span>{points[0]?.date.slice(5)}</span><span>{points[Math.floor(points.length / 2)]?.date.slice(5)}</span><span>{points.at(-1)?.date.slice(5)}</span></div></div>
  );
}
