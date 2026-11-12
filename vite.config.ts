import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const runtimeEnv = (
  globalThis as typeof globalThis & {
    process?: { env?: Record<string, string | undefined> };
  }
).process?.env ?? {};
const repositoryName = runtimeEnv.GITHUB_REPOSITORY?.split('/')[1];
const isGitHubProjectPage =
  runtimeEnv.GITHUB_ACTIONS === 'true' &&
  Boolean(repositoryName) &&
  !repositoryName?.endsWith('.github.io');
const base =
  isGitHubProjectPage && repositoryName ? `/${repositoryName}/` : '/';

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
  },
});
