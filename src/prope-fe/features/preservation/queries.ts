import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { preservedPromptSchema, promptFormSchema, promptListSchema, type PreservedPrompt, type PromptFormValues } from '@/features/preservation/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 280));

let mockPrompts: PreservedPrompt[] = promptListSchema.parse([
  {
    id: 'customer-insight-summary', title: 'Tóm tắt phỏng vấn khách hàng',
    purpose: 'Chuyển ghi chú phỏng vấn thành insight có thể hành động.',
    content: 'Phân tích ghi chú phỏng vấn dưới đây. Nhóm các phát hiện theo nhu cầu, nỗi đau, hành vi và cơ hội. Chỉ nêu kết luận có bằng chứng trực tiếp.',
    tags: ['Nghiên cứu', 'Tóm tắt'], status: 'approved', source: 'manual', modelName: 'research/customer-insight-summary', providerName: 'OpenAI Primary', upstreamModel: 'gpt-5.2', temperature: 0.2, maxTokens: 1600, fallbackAnswer: 'Không thể tạo bản tóm tắt lúc này. Vui lòng thử lại sau.', ownerId: 'linh', ownerName: 'Linh Nguyễn', access: 'private', createdAt: '2026-08-02T09:00:00.000Z', updatedAt: '2026-08-10T08:30:00.000Z', reuseCount: 12, currentRevision: 3, currentVersionId: 'customer-insight-summary-revision-3', trustedRevision: 3, trustedVersionId: 'customer-insight-summary-revision-3', releasedRevision: 2, releasedVersionId: 'customer-insight-summary-revision-2',
  },
  {
    id: 'release-note-draft', title: 'Bản nháp ghi chú phát hành',
    purpose: 'Tạo ghi chú phát hành rõ ràng từ danh sách thay đổi kỹ thuật.',
    content: 'Viết ghi chú phát hành ngắn gọn từ danh sách thay đổi. Tách phần tính năng mới, cải tiến và sửa lỗi; ưu tiên lợi ích cho người dùng.',
    tags: ['Sản phẩm', 'Nội dung'], status: 'draft', source: 'manual', modelName: 'product/release-note-draft', providerName: 'OpenAI Primary', upstreamModel: 'gpt-5.2-mini', temperature: 0.4, maxTokens: 1200, fallbackAnswer: 'Không thể tạo ghi chú phát hành lúc này.', ownerId: 'linh', ownerName: 'Linh Nguyễn', access: 'private', createdAt: '2026-08-07T03:20:00.000Z', updatedAt: '2026-08-09T04:10:00.000Z', reuseCount: 3, currentRevision: 1, currentVersionId: 'release-note-draft-revision-1', trustedRevision: null, trustedVersionId: null, releasedRevision: null, releasedVersionId: null,
  },
  {
    id: 'support-triage', title: 'Phân loại yêu cầu hỗ trợ',
    purpose: 'Định tuyến yêu cầu hỗ trợ theo mức độ ưu tiên và chủ đề.',
    content: 'Đọc yêu cầu hỗ trợ, xác định chủ đề, mức độ khẩn cấp và nhóm phụ trách. Trả về lý do ngắn gọn và không suy đoán dữ liệu còn thiếu.',
    tags: ['Vận hành'], status: 'inReview', source: 'manual', modelName: 'support/triage', providerName: 'Azure OpenAI', upstreamModel: 'gpt-4.1', temperature: 0.1, maxTokens: 900, fallbackAnswer: 'Yêu cầu chưa thể được phân loại tự động. Vui lòng chuyển cho nhân viên hỗ trợ.', ownerId: 'linh', ownerName: 'Linh Nguyễn', access: 'private', createdAt: '2026-07-28T01:15:00.000Z', updatedAt: '2026-08-08T07:45:00.000Z', reuseCount: 28, currentRevision: 4, currentVersionId: 'support-triage-revision-4', trustedRevision: null, trustedVersionId: null, releasedRevision: null, releasedVersionId: null,
  },
]);

async function readMockPrompts() { await wait(); return promptListSchema.parse(mockPrompts); }
async function readMockPrompt(id: string) {
  await wait();
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  return preservedPromptSchema.parse(prompt);
}
async function createMockPrompt(values: PromptFormValues) {
  await wait();
  const data = promptFormSchema.parse(values);
  const now = new Date().toISOString();
  const id = `${Date.now()}`;
  const prompt = preservedPromptSchema.parse({ id, title: data.title, purpose: data.purpose, content: data.content, tags: data.tags.split(',').map((tag) => tag.trim()).filter(Boolean), status: 'draft', source: data.source, modelName: data.modelName, providerName: data.providerName, upstreamModel: data.upstreamModel, temperature: data.temperature, maxTokens: data.maxTokens, fallbackAnswer: data.fallbackAnswer, ownerId: data.ownerId, ownerName: data.ownerName, access: data.access, createdAt: now, updatedAt: now, reuseCount: 0, currentRevision: 1, currentVersionId: `${id}-revision-1`, trustedRevision: null, trustedVersionId: null, releasedRevision: null, releasedVersionId: null });
  mockPrompts = [prompt, ...mockPrompts];
  return prompt;
}
async function reuseMockPrompt(id: string) {
  await wait();
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  const reused = { ...prompt, reuseCount: prompt.reuseCount + 1, updatedAt: new Date().toISOString() };
  mockPrompts = mockPrompts.map((item) => item.id === id ? reused : item);
  return preservedPromptSchema.parse(reused);
}

export function applyMockRevision(id: string, revision: Pick<PreservedPrompt, 'content' | 'providerName' | 'upstreamModel' | 'temperature' | 'maxTokens' | 'fallbackAnswer'> & { number?: number; versionId?: string }, updatedAt: string) {
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  const currentRevision = revision.number ?? prompt.currentRevision + 1;
  const updated = preservedPromptSchema.parse({ ...prompt, ...revision, status: 'draft', updatedAt, currentRevision, currentVersionId: revision.versionId ?? `${id}-revision-${currentRevision}` });
  mockPrompts = mockPrompts.map((item) => item.id === id ? updated : item);
  return updated;
}

export function applyMockPromptStatus(id: string, status: PreservedPrompt['status']) {
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  const updated = preservedPromptSchema.parse({ ...prompt, status, updatedAt: new Date().toISOString(), trustedRevision: status === 'approved' ? prompt.currentRevision : prompt.trustedRevision, trustedVersionId: status === 'approved' ? prompt.currentVersionId : prompt.trustedVersionId });
  mockPrompts = mockPrompts.map((item) => item.id === id ? updated : item);
  return updated;
}

export function applyMockRelease(id: string, revisionNumber: number, versionId: string) {
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  const updated = preservedPromptSchema.parse({ ...prompt, releasedRevision: revisionNumber, releasedVersionId: versionId, updatedAt: new Date().toISOString() });
  mockPrompts = mockPrompts.map((item) => item.id === id ? updated : item);
  return updated;
}

export function applyMockAccess(id: string, access: Pick<PreservedPrompt, 'access' | 'ownerId' | 'ownerName'>, updatedAt: string) {
  const prompt = mockPrompts.find((item) => item.id === id);
  if (!prompt) throw new Error('PROMPT_NOT_FOUND');
  const updated = preservedPromptSchema.parse({ ...prompt, ...access, updatedAt });
  mockPrompts = mockPrompts.map((item) => item.id === id ? updated : item);
  return updated;
}

export function readMockPromptsSnapshot() { return promptListSchema.parse(mockPrompts); }

export const promptKeys = {
  all: ['preserved-prompts'] as const,
  detail: (id: string) => ['preserved-prompts', id] as const,
};

export const promptListOptions = queryOptions({
  queryKey: promptKeys.all,
  queryFn: readMockPrompts,
});

export const promptDetailOptions = (id: string) => queryOptions({
  queryKey: promptKeys.detail(id),
  queryFn: () => readMockPrompt(id),
});

export function useCreatePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMockPrompt,
    onSuccess: (prompt) => {
      queryClient.setQueryData(promptKeys.detail(prompt.id), prompt);
      void queryClient.invalidateQueries({ queryKey: promptKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['trusted-registry'] });
    },
  });
}

export function useReusePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reuseMockPrompt,
    onSuccess: (prompt) => {
      queryClient.setQueryData(promptKeys.detail(prompt.id), prompt);
      void queryClient.invalidateQueries({ queryKey: promptKeys.all });
    },
  });
}
