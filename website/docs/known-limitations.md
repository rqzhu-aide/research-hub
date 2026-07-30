---
sidebar_position: 5
title: "Current Limitations"
slug: /known-limitations
---

# Current Limitations

Research Hub is under active development. This page records limitations that
affect how you use the current `main` branch.

## Legacy review-only records are read-only

Projects created by an earlier version may contain review-only Phase 5 records.
They remain available in run history for provenance, but the current interface
does not launch or relaunch that legacy path. Use **Review & Revision** to review
the branch's current `manuscript.md` and replace it with a revised current
manuscript in one user-started run.

## Context selection is phase-specific

Research Hub does not provide a file-by-file context picker. Each phase instead
uses a storage rule that keeps its normal input compact:

- Phase 1 searches against the cumulative reference library and adds a validated
  delta of new sources.
- Phase 2 lets you update the full catalog or focus on one active method.
- Phase 3 uses the current theory and empirical records by default. You may also
  include archived Phase 3 summaries when they exist.
- Phase 4 uses the cumulative evidence index and current empirical synthesis.
- Phase 5 uses the verified current records from Phases 1 through 4 and one
  current branch manuscript.

Individual archived artifacts cannot currently be selected one by one. Use the
available phase scope or context option, and state any narrower scientific focus
in the run instructions.

## Platform support

Linux is the only platform on which Research Hub is currently developed and
tested. See [Operating System Support](./operating-systems) before installing it
elsewhere.
