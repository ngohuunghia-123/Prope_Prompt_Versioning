/**
 * The three copy-paste integrations, generated from the prompt in front of you.
 *
 * **Every one of them names the prompt and never the revision.** `model` is
 * `namespace/name`, so the consumer's code asks for *the prompt* and the gateway
 * serves whatever revision is released at that moment — which is the entire
 * product: a rollback is a release decision in Prope, not a redeploy in their
 * repo. The pinned form `namespace/name@3` exists and resolves an Approved
 * revision, and it is deliberately not what a first snippet teaches, because a
 * pinned client is a client a restore cannot reach.
 *
 * **They will not work until the prompt is released**, and the screen says so
 * rather than the code pretending otherwise. A draft has no released pointer, so
 * the gateway answers the same not-found it gives an unknown model name.
 */

export interface SnippetInput {
  /** `namespace/name` — what the consumer passes as `model`. */
  modelName: string;
  /** The page's own origin, so a copied snippet points at the install it came from. */
  baseUrl: string;
  /** The real secret when it has just been minted; a masked placeholder otherwise. */
  apiKey: string;
  /** `{{variable}}` names the body needs. Empty for most prompts. */
  variables: string[];
}

export type SnippetLanguage = 'python' | 'nextjs' | 'curl';

export const SNIPPET_LANGUAGES: readonly SnippetLanguage[] = ['python', 'nextjs', 'curl'];

const FILENAMES: Record<SnippetLanguage, string> = {
  python: 'prope_example.py',
  nextjs: 'app/api/chat/route.ts',
  curl: 'prope.sh',
};

export function snippetFilename(language: SnippetLanguage): string {
  return FILENAMES[language];
}

/** `{"a": "…", "b": "…"}` in whichever language's object syntax. */
function variableObject(variables: string[], quote: (name: string) => string): string {
  if (variables.length === 0) return '';
  return variables.map((name) => `${quote(name)}: "..."`).join(', ');
}

function pythonSnippet(input: SnippetInput): string {
  const variables = variableObject(input.variables, (name) => `"${name}"`);
  const extra = variables
    ? `\n    extra_body={"prope": {"variables": {${variables}}}},`
    : '';
  return `# pip install openai
from openai import OpenAI

client = OpenAI(
    base_url="${input.baseUrl}/v1",
    api_key="${input.apiKey}",
)

response = client.chat.completions.create(
    model="${input.modelName}",
    messages=[{"role": "user", "content": "Xin chào"}],${extra}
)

print(response.choices[0].message.content)
# The revision that served this call, for your logs:
print(response.model_extra["prope"]["version_id"])`;
}

function nextjsSnippet(input: SnippetInput): string {
  const variables = variableObject(input.variables, (name) => `"${name}"`);
  const extra = variables ? `\n      prope: { variables: { ${variables} } },` : '';
  return `// npm install openai
// app/api/chat/route.ts
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: '${input.baseUrl}/v1',
  // Never NEXT_PUBLIC_: this key must stay on the server.
  apiKey: process.env.PROPE_API_KEY,
});

export async function POST(request: Request) {
  const { message } = await request.json();

  const completion = await client.chat.completions.create({
    model: '${input.modelName}',
    messages: [{ role: 'user', content: message }],${extra}
  });

  return Response.json({ reply: completion.choices[0].message.content });
}`;
}

function curlSnippet(input: SnippetInput): string {
  const variables = variableObject(input.variables, (name) => `"${name}"`);
  const extra = variables ? `,\n    "prope": {"variables": {${variables}}}` : '';
  return `curl ${input.baseUrl}/v1/chat/completions \\
  -H "Authorization: Bearer ${input.apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${input.modelName}",
    "messages": [{"role": "user", "content": "Xin chào"}]${extra}
  }'`;
}

const BUILDERS: Record<SnippetLanguage, (input: SnippetInput) => string> = {
  python: pythonSnippet,
  nextjs: nextjsSnippet,
  curl: curlSnippet,
};

export function buildSnippet(language: SnippetLanguage, input: SnippetInput): string {
  return BUILDERS[language](input);
}

/**
 * Where the copied code should point.
 *
 * `window.location.origin` rather than a configured value: the SPA and the
 * gateway share one origin by construction — Caddy dispatches `/v1/*` and
 * `/api/*` to the same upstream, which is what lets the session cookie work with
 * no CORS anywhere in Prope. A snippet copied from this install therefore points
 * at this install, whether that is `localhost:8080` or the customer's domain.
 */
export function gatewayBaseUrl(): string {
  if (typeof window === 'undefined') return '';
  return window.location.origin;
}
