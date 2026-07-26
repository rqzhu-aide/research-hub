import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Getting Started',
      items: ['intro', 'install', 'quickstart'],
    },
    {
      type: 'category',
      label: 'Research Workflow',
      items: [
        'workflow/overview',
        'workflow/phase-1-literature',
        'workflow/phase-2-methods',
        'workflow/phase-3-evaluation',
        'workflow/phase-4-draft',
        'workflow/phase-5-review',
      ],
    },
    {
      type: 'category',
      label: 'Roles & Team',
      items: [
        'roles/overview',
        'roles/research-lead',
        'roles/theorist',
        'roles/data-scientist',
        'roles/paper-reviewer',
      ],
    },
    {
      type: 'category',
      label: 'Core Concepts',
      items: [
        'concepts/control-model',
        'concepts/method-registry',
        'concepts/reruns',
        'concepts/method-branches',
        'concepts/integrity',
      ],
    },
    {
      type: 'category',
      label: 'Configuration',
      items: [
        'config/hub-agents',
        'config/phases',
        'config/souls',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/launch-pipeline',
        'architecture/sealed-manifests',
      ],
    },
  ],
};

export default sidebars;
