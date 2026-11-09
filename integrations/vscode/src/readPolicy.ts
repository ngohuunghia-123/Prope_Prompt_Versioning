import { z } from 'zod';
import { ConnectorError } from './api';

export function allowedRead(payload: unknown) {
  const path = z.string().max(2000).parse(payload);
  const url = new URL(path, 'http://127.0.0.1');
  if (url.origin !== 'http://127.0.0.1' || url.hash || /%2f|%5c|[\\\r\n]/i.test(path)) throw new ConnectorError('read_denied', 403);
  const route = decodeURIComponent(url.pathname);
  const id = '[a-zA-Z0-9_:@.-]+';
  const allowed = [
    /^\/api\/v1\/chat\/pipeline$/,
    /^\/api\/v1\/(folders|prompts|providers|datasets)$/,
    new RegExp(`^/api/v1/prompts/${id}(/revisions|/dataset-attachments|/eval-comparisons)?$`),
    new RegExp(`^/api/v1/revisions/${id}$`),
    new RegExp(`^/api/v1/providers/${id}/models$`),
    new RegExp(`^/api/v1/datasets/${id}$`),
    new RegExp(`^/api/v1/prompts/${id}/eval-runs$`),
    new RegExp(`^/api/v1/eval-runs/${id}(/cases)?$`),
    new RegExp(`^/api/v1/eval-runs/${id}/cases/${id}/trace$`),
    new RegExp(`^/api/v1/eval-suites/${id}$`),
    /^\/api\/v1\/agent-runs$/,
    new RegExp(`^/api/v1/agent-runs/${id}$`),
  ];
  if (!allowed.some((pattern) => pattern.test(route))) throw new ConnectorError('read_denied', 403);
  return `${url.pathname}${url.search}`;
}
