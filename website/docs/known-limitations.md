---
sidebar_position: 5
title: "Current Limitations"
slug: /known-limitations
---

# Current Limitations

Research Hub is under active development. This page records limitations that
affect how you use the current `main` branch.

## Review & Revision has a legacy launch gate

Phase 5 Review & Revision still requires a same-branch Assembly run whose record
has the legacy `approved` status. The current phase panel does not provide an
approval action, so a newly completed Assembly run cannot normally satisfy this
gate. Existing projects may contain an eligible record created by an earlier
interface.

This is a current implementation restriction, not a scientific judgment and
not the intended long-term run policy. Assembly can still create or rebuild a
manuscript, but the current Web UI has no supported path from a newly completed
Assembly directly into the combined reviewer-and-revision run.

A later Phase 5 result can also cause an older eligible Assembly record to stop
satisfying the gate, which restricts repeated Review & Revision cycles.

## Review target is review-only

The Phase 5 **Review target** option gives the Paper Reviewer a manuscript-only
first reading, followed by an assessment informed by the internal scientific
record. It does not include a Research Lead revision stage.

Standard **Review & Revision** reviews and revises the Assembly recognized by
its legacy launch gate. It does not continue from the exact post-review
manuscript chosen as a Review target. The current interface has no one-click
action to revise that selected manuscript.

## Prior context selection is automatic

Launch forms show the prior context assembled for a run, but they do not yet
let the user include or exclude individual completed results. Research Hub
selects eligible prerequisite and same-branch material according to the current
phase rules.

If the assembled context is not suitable, do not launch the run. Rerun the
relevant phase, choose another method where applicable, or state a narrower
question that makes the intended use of the available evidence explicit.

## Platform support

Linux is the only platform on which Research Hub is currently developed and
tested. See [Operating System Support](./operating-systems) before installing it
elsewhere.
