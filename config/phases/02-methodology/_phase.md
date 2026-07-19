# Phase: Methodology

## Goal
Design a method that rigorously answers the research question identified in
the Ideation synthesis. Iterate through debate until the method is sound,
answers the question, and is implementable.

## Pattern: Debate
The **Theorist** owns this phase. Each round:
1. Theorist proposes / revises a method
2. Research Lead critiques (does it answer the question?)
3. Data Scientist critiques (can we implement it?)

Then the Theorist revises in light of both critiques. Repeat for
up to {{max_rounds}} rounds or until convergence.

## Output convention
- Proposals: `phases/02-methodology/statistician/round-NN.md`
- Critiques: `phases/02-methodology/{lead,programmer}/round-NN.md`

## What "method" means
The method specification should include:
- The estimand (what are we estimating, precisely)
- The procedure (algorithm / analysis steps)
- The assumptions it relies on
- How success is measured (what result would confirm / refute the method)
- What can go wrong (known failure modes)
