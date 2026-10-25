import { createStore, useStore } from "@/lib/store";

export interface Toast {
  id: number;
  tone: "info" | "success" | "danger" | "warning";
  title: string;
  body?: string;
  href?: string;
  actionLabel?: string;
  onAction?: () => void;
}

let seq = 0;
export const toastStore = createStore<Toast[]>([]);

export function useToasts(): Toast[] {
  return useStore(toastStore);
}

export function toast(t: Omit<Toast, "id">): number {
  const id = ++seq;
  toastStore.set((list) => [...list.slice(-4), { ...t, id }]);
  return id;
}

export function dismissToast(id: number): void {
  toastStore.set((list) => list.filter((t) => t.id !== id));
}
