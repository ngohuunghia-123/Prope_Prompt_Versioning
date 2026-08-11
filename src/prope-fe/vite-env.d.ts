/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTH_MODE?: 'api' | 'mock';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
