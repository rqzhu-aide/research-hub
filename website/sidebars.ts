import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'setup',
    'project-setup',
    {
      type: 'category',
      label: 'Research Workflow',
      items: [
        'workflow/pipeline',
        'workflow/phase-1',
        'workflow/phase-2',
        'workflow/phase-3',
        'workflow/phase-4',
        'workflow/phase-5',
      ],
    },
    'roles',
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/config',
        'reference/architecture',
      ],
    },
  ],
};

export default sidebars;
