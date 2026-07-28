import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const phases = [
  {
    num: '1',
    name: 'Literature Review',
    desc: 'Establish the relevant evidence, boundaries, and open questions.',
    href: '/docs/workflow/phase-1',
  },
  {
    num: '2',
    name: 'Method Development',
    desc: 'Develop and compare candidate contributions or methods.',
    href: '/docs/workflow/phase-2',
  },
  {
    num: '3',
    name: 'Theoretical Development',
    desc: 'Examine assumptions, proofs, rates, and failure modes.',
    href: '/docs/workflow/phase-3',
  },
  {
    num: '4',
    name: 'Implementation & Experiments',
    desc: 'Choose a method, implement it, and evaluate it under a prespecified protocol.',
    href: '/docs/workflow/phase-4',
  },
  {
    num: '5',
    name: 'Paper Assembly & Review',
    desc: 'Assemble a manuscript, review it in a separate context, and revise it.',
    href: '/docs/workflow/phase-5',
  },
];

const principles = [
  {
    title: 'You choose each run',
    body: 'Nothing starts automatically. You choose the phase, the run plan, the scientific direction, and when another run is warranted.',
  },
  {
    title: 'Evidence comes before progression',
    body: 'A completed run is material for inspection, not an automatic scientific conclusion. You decide whether its evidence is sufficient for later work.',
  },
  {
    title: 'History remains inspectable',
    body: 'Prepared runs preserve their prompt, frozen context, manifest, and log. Completed runs also retain their submitted summary, so later changes can be traced.',
  },
  {
    title: 'Roles have distinct responsibilities',
    body: 'The research lead, theorist, data analyst, and paper reviewer examine different parts of the argument and contribute at different phases.',
  },
];

type Phase = (typeof phases)[number];

function PipelinePhase({
  phase,
  sibling = false,
}: {
  phase: Phase;
  sibling?: boolean;
}) {
  return (
    <li
      className={
        sibling
          ? `${styles.pipelineRow} ${styles.siblingPhase}`
          : styles.pipelineRow
      }>
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
  );
}

function Hero() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <section className={styles.hero}>
      <div className={styles.heroLead}>
        <p className={styles.kicker}>A user-directed research pipeline</p>
        <Heading as="h1" className={styles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p className={styles.heroLead2}>
          Coordinate a team of Hermes AI agents across literature assessment,
          method development, independent theory and experiment studies, and
          manuscript preparation.
          Research Hub preserves the evidence from each run while you decide what
          should happen next.
        </p>
        <div className={styles.ctaRow}>
          <Link className={styles.ctaPrimary} to="/docs/setup">
            Set up Research Hub
          </Link>
          <Link className={styles.ctaGhost} to="/docs/workflow/pipeline">
            Understand the workflow
          </Link>
        </div>
        <p className={styles.statusNote}>
          Linux is the only supported platform. Review the{' '}
          <Link to="/docs/operating-systems">operating-system guidance</Link> before use.
        </p>
      </div>

      <ol className={styles.pipeline} aria-label="The five-phase research pipeline">
        {phases.slice(0, 2).map((phase) => (
          <PipelinePhase key={phase.num} phase={phase} />
        ))}
        <li className={styles.siblingGroup}>
          <div className={styles.siblingHeader} id="sibling-phases-label">
            <span className={styles.siblingTitle}>Sibling phases</span>
            <span className={styles.siblingNote}>
              Either can run first after Phase 2
            </span>
          </div>
          <ol
            className={styles.siblingList}
            aria-labelledby="sibling-phases-label">
            {phases.slice(2, 4).map((phase) => (
              <PipelinePhase key={phase.num} phase={phase} sibling />
            ))}
          </ol>
        </li>
        {phases.slice(4).map((phase) => (
          <PipelinePhase key={phase.num} phase={phase} />
        ))}
      </ol>
    </section>
  );
}

function Principles() {
  return (
    <section className={styles.principles}>
      <Heading as="h2" className={styles.principlesHeading}>
        Working principles
      </Heading>
      <div className={styles.principleList}>
        {principles.map((principle) => (
          <div key={principle.title} className={styles.principle}>
            <Heading as="h3" className={styles.principleTitle}>
              {principle.title}
            </Heading>
            <p className={styles.principleBody}>{principle.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="User-Directed Research Workflows with Hermes"
      description="A local Web UI for user-directed, multi-agent research workflows with preserved evidence and explicit phase choices.">
      <main>
        <Hero />
        <Principles />
      </main>
    </Layout>
  );
}
