---
title: Atlas Project
type: note
permalink: atlas-project
project: atlas
status: active
---
# Atlas Project
Objective: Build an offline field-report queue for one laptop.
Current state: Parser complete; retry behavior not yet tested.
Accepted decision: Use SQLite for the queue; see [[Queue Decision]].
Blocker: Missing sample for an empty report.
Next authorized action: Add the empty-report fixture and run the parser tests.
Deployment is not authorized.
Recovery marker: ATLAS-42.
Related: [[Queue Decision]], [[Restart Runbook]], [[Release Checklist]].
