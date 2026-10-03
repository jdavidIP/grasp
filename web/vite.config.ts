/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // Lets React Testing Library find afterEach and unmount between tests. Tests
    // still import describe/it/expect from 'vitest' explicitly.
    globals: true,
  },
})
