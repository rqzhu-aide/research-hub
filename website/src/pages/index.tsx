import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

/* ── SVG icons (Lucide-style) — no emojis, per anti-AI-slop rules ── */
const GamepadIcon = () => (
  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="6" y1="12" x2="10" y2="12" /><line x1="8" y1="10" x2="8" y2="14" />
    <line x1="15" y1="13" x2="15.01" y2="13" /><line x1="18" y1="11" x2="18.01" y2="11" />
    <rect x="2" y="6" width="20" height="12" rx="4" />
  </svg>
);
const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);
const RefreshIcon = () => (
  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const phases = [
  { num: '1', name: 'Literature Review', desc: 'Survey prior work, identify gaps', href: '/docs/workflow/phase-1' },
  { num: '2', name: 'Method Development', desc: 'Brainstorm new mechanisms and frameworks', href: '/docs/workflow/phase-2' },
  { num: '3', name: 'Idea Evaluation', desc: 'Prove theorems, establish rate bounds', href: '/docs/workflow/phase-3' },
  { num: '4', name: 'Draft Assembly', desc: 'Write the paper with experiments', href: '/docs/workflow/phase-4' },
  { num: '5', name: 'Review & Revision', desc: 'Independent audit and final revision', href: '/docs/workflow/phase-5' },
];

const features = [
  { title: 'User-In-Control', Icon: GamepadIcon, desc: 'Nothing advances automatically. You start every run, review every result, and make every decision.' },
  { title: 'Sealed Integrity', Icon: ShieldIcon, desc: 'Every run\'s inputs are frozen and SHA-256 hashed. Fully reproducible, tamper-evident, auditable.' },
  { title: 'Iterative Refinement', Icon: RefreshIcon, desc: 'Reruns audit and extend prior work. Methods get permanent numbers that survive retirement and merge.' },
  { title: 'Multi-Agent Teams', Icon: UsersIcon, desc: 'Four specialized roles (theorist, lead, data scientist, reviewer) collaborate in structured rounds.' },
];

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <p className="hero__subtitle" style={{fontSize: '1.1em', maxWidth: '700px', margin: '0 auto'}}>
          A structured research pipeline that turns the process of doing research —
          from literature review to published manuscript — into a reproducible,
          auditable, multi-agent workflow. Built on Hermes Agent.
        </p>
        <div className={styles.buttons}>
          <Link
            className="button button--primary button--lg"
            to="/docs/setup">
            Get Started →
          </Link>
          <Link
            className="button button--outline button--lg button--secondary"
            to="/docs/workflow/pipeline"
            style={{marginLeft: '10px'}}>
            How It Works
          </Link>
        </div>
      </div>
    </header>
  );
}

function PhasePipeline() {
  return (
    <div className="container padding-vert--lg">
      <Heading as="h2" className="text--center margin-bottom--lg">
        The Five-Phase Research Pipeline
      </Heading>
      <div className={styles.pipelineGrid}>
        {phases.map((phase) => (
          <Link key={phase.num} to={phase.href} className={styles.phaseCard}>
            <span className={styles.phaseNumber}>{phase.num}</span>
            <Heading as="h4" style={{marginBottom: '4px'}}>{phase.name}</Heading>
            <p style={{fontSize: '0.85em', margin: 0, color: 'var(--ifm-font-color-tertiary)'}}>
              {phase.desc}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Features() {
  return (
    <div className="container padding-vert--lg">
      <div className={styles.features}>
        {features.map(({title, Icon, desc}) => (
          <div key={title} className={styles.featureCard}>
            <div className={styles.featureIcon} style={{color: 'var(--ifm-color-primary)'}}>
              <Icon />
            </div>
            <Heading as="h4">{title}</Heading>
            <p style={{fontSize: '0.9em', color: 'var(--ifm-font-color-secondary)'}}>{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Research Hub — Structured Multi-Agent Research Workflows"
      description="A local Web UI for running structured, multi-agent research workflows with Hermes. Five-phase pipeline from literature review to published manuscript.">
      <HomepageHeader />
      <main>
        <PhasePipeline />
        <Features />
      </main>
    </Layout>
  );
}
