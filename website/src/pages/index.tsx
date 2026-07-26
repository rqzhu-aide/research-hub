import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const phases = [
  { num: '1', name: 'Literature Review', desc: 'Survey prior work, identify gaps', href: '/docs/workflow/phase-1' },
  { num: '2', name: 'Method Development', desc: 'Brainstorm new mechanisms and frameworks', href: '/docs/workflow/phase-2' },
  { num: '3', name: 'Idea Evaluation', desc: 'Prove theorems, establish rate bounds', href: '/docs/workflow/phase-3' },
  { num: '4', name: 'Draft Assembly', desc: 'Write the paper with experiments', href: '/docs/workflow/phase-4' },
  { num: '5', name: 'Review & Revision', desc: 'Independent audit and final revision', href: '/docs/workflow/phase-5' },
];

const features = [
  {
    title: 'User-In-Control',
    icon: '🎮',
    desc: 'Nothing advances automatically. You start every run, review every result, and make every decision.',
  },
  {
    title: 'Sealed Integrity',
    icon: '🔒',
    desc: 'Every run\'s inputs are frozen and SHA-256 hashed. Fully reproducible, tamper-evident, auditable.',
  },
  {
    title: 'Iterative Refinement',
    icon: '🔄',
    desc: 'Reruns audit and extend prior work. Methods get permanent numbers that survive retirement and merge.',
  },
  {
    title: 'Multi-Agent Teams',
    icon: '👥',
    desc: 'Four specialized roles (theorist, lead, data scientist, reviewer) collaborate in structured rounds.',
  },
];

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
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
            className="button button--secondary button--lg"
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
      <div className="row">
        {phases.map((phase) => (
          <div key={phase.num} className="col col--2_4" style={{flexBasis: '20%'}}>
            <Link to={phase.href} className="card padding--lg" style={{height: '100%', display: 'block', textDecoration: 'none', color: 'inherit'}}>
              <div className="text--center margin-bottom--sm">
                <span style={{fontSize: '2.5em', fontWeight: 'bold', color: 'var(--ifm-color-primary)'}}>
                  {phase.num}
                </span>
              </div>
              <Heading as="h4" className="text--center">{phase.name}</Heading>
              <p className="text--center" style={{fontSize: '0.9em'}}>{phase.desc}</p>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

function Features() {
  return (
    <div className="container padding-vert--lg">
      <div className="row">
        {features.map((feat) => (
          <div key={feat.title} className="col col--3">
            <div className="card padding--lg margin-bottom--lg" style={{height: '100%'}}>
              <div style={{fontSize: '2em', marginBottom: '0.5em'}}>{feat.icon}</div>
              <Heading as="h4">{feat.title}</Heading>
              <p style={{fontSize: '0.9em'}}>{feat.desc}</p>
            </div>
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
