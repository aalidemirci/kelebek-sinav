// TanStack Query — tek QueryClient singleton'ı.
//
// Tasarım:
// - staleTime 30 sn → ekran içi pencere değiştirmede gereksiz refetch yok.
// - gcTime 5 dk → kullanılmayan veri belleğin bir süre RAM'de kalır.
// - retry 1 → 401/403/404'te retry istemiyoruz; ApiError için kontrol ediyoruz.
// - refetchOnWindowFocus false → LAN'da kullanıcı sekme değiştirince fazladan
//   istek atmayalım; pencere odakta zaten staleTime takip eder.
//
// Mevcut `lib/api.ts` korunur — TanStack onu sarar. Component'ler `useQuery`'ye
// `queryFn: () => api.get(...)` veriyor, böylece 401 refresh mantığı aynen
// çalışır.

import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Bir kez yenilemeden sonra retry istemiyoruz. 4xx hatalarında hiç.
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false;
        }
        return failureCount < 1;
      },
    },
    mutations: {
      // Mutasyonlarda retry yok — kullanıcıya hata gösterilir, manuel tekrar.
      retry: false,
    },
  },
});
