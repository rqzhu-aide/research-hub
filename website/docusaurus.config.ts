import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const config: Config = {
  title: 'Research Hub',
  tagline: 'User-directed research workflows with Hermes',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://rqzhu-aide.github.io',
  baseUrl: '/research-hub/',
  organizationName: 'rqzhu-aide',
  projectName: 'research-hub',

  onBrokenLinks: 'throw',
  onDuplicateRoutes: 'throw',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
      onBrokenMarkdownImages: 'throw',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/rqzhu-aide/research-hub/edit/main/website/',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      },
    ],
  ],

  themes: ['@docusaurus/theme-mermaid'],

  stylesheets: [
    {
      href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap',
      rel: 'stylesheet',
    },
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    mermaid: {
      theme: {
        light: 'neutral',
        dark: 'dark',
      },
    },
    navbar: {
      title: 'Research Hub',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          to: '/docs/setup',
          label: 'Setup',
          position: 'left',
        },
        {
          href: 'https://github.com/rqzhu-aide/research-hub',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Start',
          items: [
            {
              label: 'Setup',
              to: '/docs/setup',
            },
            {
              label: 'Operating System Support',
              to: '/docs/operating-systems',
            },
            {
              label: 'Create a Project',
              to: '/docs/project-setup',
            },
          ],
        },
        {
          title: 'Use Research Hub',
          items: [
            {
              label: 'Workflow Overview',
              to: '/docs/workflow/pipeline',
            },
            {
              label: 'Review Results and Choose',
              to: '/docs/workflow/decisions',
            },
            {
              label: 'Current Limitations',
              to: '/docs/known-limitations',
            },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/rqzhu-aide/research-hub',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Research Hub.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
