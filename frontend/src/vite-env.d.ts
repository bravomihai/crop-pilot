/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_USE_EXAMPLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
