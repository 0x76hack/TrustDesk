import { apiFetch } from './client';
import type { Customer, Order } from '../types/ticket';

export interface HealthCheckResponse {
  status: string;
  checks: {
    database: boolean | string;
    redis: boolean | string;
  };
}

export async function checkHealth(): Promise<HealthCheckResponse> {
  return apiFetch<HealthCheckResponse>('/health');
}

export async function listCustomers(): Promise<Customer[]> {
  return apiFetch<Customer[]>('/admin/customers');
}

export async function listOrders(): Promise<Order[]> {
  return apiFetch<Order[]>('/admin/orders');
}
