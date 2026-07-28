import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Get Started',
      collapsed: false,
      items: [
        'system-requirements',
        'operating-systems',
        'setup',
        'profile-setup',
        'project-setup',
        'operation-modes',
        'known-limitations',
      ],
    },
    {
      type: 'category',
      label: 'Research Team',
      collapsed: false,
      items: [
        'roles',
        'team-resources',
      ],
    },
    {
      type: 'category',
      label: 'Run Your Research',
      collapsed: false,
      link: {
        type: 'generated-index',
        title: 'Research Workflow',
        description: 'Understand each phase, inspect its evidence, and choose what happens next.',
        slug: '/workflow',
      },
      items: [
        'workflow/pipeline',
        'workflow/decisions',
        'workflow/phase-1',
        'workflow/phase-2',
        'workflow/phase-3',
        'workflow/phase-4',
        'workflow/phase-5',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/files-and-records',
        'reference/config',
        'reference/architecture',
      ],
    },
  ],
};

export default sidebars;
