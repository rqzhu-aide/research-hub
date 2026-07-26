import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

/* Hallmark · macrostructure: split-hero + inline-pipeline + editorial-principles
 * tone: technical-editorial · theme: locked-indigo (design-system: hub palette)
 * display: IBM Plex Serif 600 · body: IBM Plex Sans · enrichment: none
 * differs from prior (centered-hero + 3-col-grid) on: layout, hierarchy, rhythm
 */

const phases = [
  { num: '1', name: 'Literature Review', desc: 'Survey prior work, identify the gaps your project addresses.', href: '/docs/workflow/phase-1' },
  { num: '2', name: 'Method Development', desc: 'Brainstorm genuinely new mechanisms and frameworks.', href: '/docs/workflow/phase-2' },
  { num: '3', name: 'Idea Evaluation', desc: 'Prove theorems, establish rate bounds, stress-test the theory.', href: '/docs/workflow/phase-3' },
  { num: '4', name: 'Draft Assembly', desc: 'Write the paper — every role drafts their sections.', href: '/docs/workflow/phase-4' },
  { num: '5', name: 'Review & Revision', desc: 'Independent audit, then final revision to a manuscript.', href: '/docs/workflow/phase-5' },
];

const principles = [
  {
    title: 'You stay in control',
    body: 'Nothing advances automatically. You start every run, review every result, and make every decision. The system never decides for you — it prepares, you choose.',
  },
  {
    title: 'Every run is sealed',
    body: 'Inputs are frozen and SHA-256 hashed at launch. Each run is fully reproducible and tamper-evident — you can trace any claim back to the exact prompt, context, and method that produced it.',
  },
  {
    title: 'Refinement, not replacement',
    body: 'Reruns audit and extend prior work rather than overwriting it. Methods keep permanent numbers that survive retirement and merge, so the history of an idea is never lost.',
  },
  {
    title: 'A team, not a chatbot',
    body: 'Four specialized roles — theorist, research lead, data scientist, paper reviewer — collaborate in structured rounds. Each has a durable identity and a lane; they disagree, concede, and build on each other.',
  },
];

function Hero() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <section className={styles.hero}>
      <div className={styles.heroLead}>
        <p className={styles.kicker}>A multi-agent research pipeline</p>
        <Heading as="h1" className={styles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p className={styles.heroLead2}>
          A structured pipeline that turns the process of doing research — from
          literature review to published manuscript — into a reproducible,
          auditable, multi-agent workflow. Built on Hermes Agent.
        </p>
        <div className={styles.ctaRow}>
          <Link className={styles.ctaPrimary} to="/docs/setup">
            Get started
          </Link>
          <Link className={styles.ctaGhost} to="/docs/workflow/pipeline">
            How it works →
          </Link>
        </div>
      </div>

      <ol className={styles.pipeline} aria-label="The five-phase research pipeline">
        {phases.map((phase) => (
          <li key={phase.num} className={styles.pipelineRow}>
            <Link to={phase.href} className={styles.pipelineLink}>
              <span className={styles.pipelineDot} aria-hidden="true" />
              <span className={styles.pipelineBody}>
                <span className={styles.pipelineName}>
                  <span className={styles.pipelineNum}>{phase.num}</span>
                  {phase.name}
                </span>
                <span className={styles.pipelineDesc}>{phase.desc}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Principles() {
  return (
    <section className={styles.principles}>
      <Heading as="h2" className={styles.principlesHeading}>
        Principles
      </Heading>
      <div className={styles.principleList}>
        {principles.map((p, i) => (
          <div key={p.title} className={styles.principle}>
            <Heading as="h3" className={styles.principleTitle}>{p.title}</Heading>
            <p className={styles.principleBody}>{p.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Research Hub — Structured Multi-Agent Research Workflows"
      description="A local Web UI for running structured, multi-agent research workflows with Hermes. Five-phase pipeline from literature review to published manuscript.">
      <main>
        <Hero />
        <Principles />
      </main>
    </Layout>
  );
}
