import { z } from 'zod';

import { reviewTaskSchema, type ReviewTask } from '@/features/prompt-lifecycle/releaseTypes';
import { apiRequest } from '@/lib/apiClient';

const reviewTasksSchema = z.array(reviewTaskSchema);

/** The MVP notification surface is the in-app review queue (A-071). */
export async function getNotifications(): Promise<ReviewTask[]> {
  return apiRequest('/api/v1/review-tasks?limit=50', {
    schema: reviewTasksSchema,
  });
}

/**
 * The open queue only. The server filters on `status`, so the count a dashboard
 * tile shows is the array's length — not a page of mixed rows narrowed here.
 */
export async function getOpenReviewTasks(): Promise<ReviewTask[]> {
  return apiRequest('/api/v1/review-tasks?status=open&limit=20', {
    schema: reviewTasksSchema,
  });
}
