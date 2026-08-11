import { queryOptions } from '@tanstack/react-query';
import { readMockPromptsSnapshot } from '@/features/preservation/queries';
import type { PreservedPrompt } from '@/features/preservation/types';
import { registryPromptListSchema, registryPromptSchema } from '@/features/trusted-registry/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 320));

const referenceRegistry = registryPromptListSchema.parse([
  {
    id: 'checkout-assistant', title: 'Trợ lý thanh toán', purpose: 'Hướng dẫn khách hàng xử lý lỗi thanh toán theo chính sách hiện hành.',
    content: 'Phân loại lỗi thanh toán từ ngữ cảnh được cung cấp. Chỉ đề xuất bước xử lý đã được phê duyệt và nêu rõ khi cần chuyển cho nhân viên hỗ trợ.',
    tags: ['Thương mại', 'Hỗ trợ'], ownerName: 'Linh Nguyễn', modelName: 'commerce/checkout-assistant', status: 'inUse', accessLevel: 'team', revisionTrust: 'trusted', currentRevision: 8, trustedRevision: 7, trustedVersionId: 'checkout-assistant-revision-7', updatedAt: '2026-08-10T08:30:00.000Z',
  },
  {
    id: 'support-triage-registry', title: 'Phân loại yêu cầu hỗ trợ', purpose: 'Định tuyến yêu cầu hỗ trợ theo mức độ ưu tiên và nhóm phụ trách.',
    content: 'Xác định chủ đề, mức độ khẩn cấp và nhóm phụ trách. Không suy đoán dữ liệu còn thiếu và luôn nêu lý do định tuyến.',
    tags: ['Vận hành', 'CSKH'], ownerName: 'An Trần', modelName: 'support/priority-triage', status: 'approved', accessLevel: 'organization', revisionTrust: 'trusted', currentRevision: 4, trustedRevision: 4, trustedVersionId: 'support-triage-registry-revision-4', updatedAt: '2026-08-09T04:10:00.000Z',
  },
  {
    id: 'catalog-enrichment', title: 'Bổ sung danh mục', purpose: 'Chuẩn hóa mô tả sản phẩm trước khi xuất bản lên danh mục.',
    content: 'Tạo mô tả sản phẩm theo schema danh mục và giữ nguyên mọi thông số kỹ thuật từ nguồn.',
    tags: ['Nội dung', 'Danh mục'], ownerName: 'Mai Lê', modelName: 'catalog/enrichment', status: 'inReview', accessLevel: 'team', revisionTrust: 'untrusted', currentRevision: 3, trustedRevision: null, trustedVersionId: null, updatedAt: '2026-08-08T07:45:00.000Z',
  },
]);

function fromPreservedPrompt(prompt: PreservedPrompt) {
  return registryPromptSchema.parse({
    id: prompt.id, title: prompt.title, purpose: prompt.purpose, content: prompt.content, tags: prompt.tags,
    ownerName: prompt.ownerName, modelName: prompt.modelName,
    status: prompt.releasedVersionId ? 'inUse' : prompt.status,
    accessLevel: prompt.access,
    revisionTrust: prompt.trustedVersionId ? 'trusted' : 'untrusted',
    currentRevision: prompt.currentRevision,
    trustedRevision: prompt.trustedRevision,
    trustedVersionId: prompt.trustedVersionId,
    updatedAt: prompt.updatedAt,
  });
}

async function readRegistry() {
  await wait();
  const live = readMockPromptsSnapshot().map(fromPreservedPrompt);
  return registryPromptListSchema.parse([...live, ...referenceRegistry.filter((reference) => !live.some((prompt) => prompt.id === reference.id))]);
}
async function readRegistryPrompt(id: string) {
  const prompt = (await readRegistry()).find((item) => item.id === id);
  if (!prompt) throw new Error('REGISTRY_PROMPT_NOT_FOUND');
  return registryPromptSchema.parse(prompt);
}

export const registryKeys = {
  all: ['trusted-registry'] as const,
  detail: (id: string) => ['trusted-registry', id] as const,
};

export const registryListOptions = queryOptions({ queryKey: registryKeys.all, queryFn: readRegistry });
export const registryDetailOptions = (id: string) => queryOptions({ queryKey: registryKeys.detail(id), queryFn: () => readRegistryPrompt(id) });
