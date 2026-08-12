import { queryOptions, useMutation } from '@tanstack/react-query';
import { similarCheckFormSchema, similarCheckResultSchema } from '@/features/similar-check/types';

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 400));

async function readAvailability() {
  await wait();
  return { available: true };
}

async function checkSimilar(input: unknown) {
  await wait();
  const values = similarCheckFormSchema.parse(input);
  if (values.title.toLowerCase().includes('error')) throw new Error('SIMILAR_CHECK_FAILED');
  const noMatches = values.title.toLowerCase().includes('unique');
  return similarCheckResultSchema.parse({ matches: noMatches ? [] : [
    { id: 'customer-insight-summary', title: 'Tóm tắt phỏng vấn khách hàng', purpose: 'Chuyển ghi chú phỏng vấn thành insight có thể hành động.', score: 91, ownerName: 'Linh Nguyễn' },
    { id: 'support-triage', title: 'Phân loại yêu cầu hỗ trợ', purpose: 'Định tuyến yêu cầu hỗ trợ theo mức độ ưu tiên và chủ đề.', score: 72, ownerName: 'Linh Nguyễn' },
  ] });
}

export const similarAvailabilityOptions = queryOptions({ queryKey: ['similar-check-availability'], queryFn: readAvailability });
export function useCheckSimilar() { return useMutation({ mutationFn: checkSimilar }); }
