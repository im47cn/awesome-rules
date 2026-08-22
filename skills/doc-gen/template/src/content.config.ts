import { docsLoader, i18nLoader } from "@astrojs/starlight/loaders";
import { docsSchema, i18nSchema } from "@astrojs/starlight/schema";
import { defineCollection } from "astro:content";

// 回归 Starlight 原生：仅保留 docs / i18n 两个原生 collection，移除 Dockit 的 ctaSection。
export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema(),
  }),
  i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() }),
};
