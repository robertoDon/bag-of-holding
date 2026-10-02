# Deploy Runbook

## Introduction

This document is intended to serve as the primary reference for anyone on the team who
needs to deploy the service to production. It is important to read it carefully before
your first deploy, and it is also a good idea to come back to it from time to time, since
the process does evolve and we want everyone to stay aligned on how things work. In the
sections below we will cover when you can deploy, what you need to do beforehand, how the
canary works, and what to do if something goes wrong.

## When you can deploy

Please note that deploys to production are only allowed on Tuesday and Thursday, and only
between 10:00 and 15:00 UTC. We chose these windows because they are the times when the
largest number of engineers are online and available to help if something unexpected
happens, which in our experience makes incidents much shorter and much less stressful for
everyone involved. Outside of these windows, deploys are not allowed.

It should go without saying, but just to be completely clear: you should never deploy on a
Friday, under any circumstances. On 2025-11-14 a Friday deploy went wrong and it cost us 3
hours of downtime, because most of the people who could have helped had already logged off
for the weekend. We really do not want to repeat that experience.

Hotfixes are a special case. A hotfix is exempt from the deploy window described above,
which means it can go out on any day and at any time, but keep in mind that a hotfix still
needs to pass `make preflight` just like any other deploy does.

## Before you deploy

Before every single deploy, without exception, you need to run `make preflight`. This
command runs the full test suite, checks the migrations, and validates the configuration.
It is really important not to skip this step, even if you are confident that your change
is small and safe, because small and safe changes are exactly the ones that tend to
surprise us.

As a general rule, the build artifact must not be larger than 400 MB. If it is larger than
that, the deploy pipeline will reject it, so it is worth checking the size before you
start, which will save you time.

If your change includes a database migration, please be aware that it needs approval from
two reviewers before it can be deployed. One reviewer is not enough for migrations, even
though one reviewer is enough for regular code changes.

Feature flags, in case you are wondering where they are kept, live in `config/flags.yaml`.
You can toggle a flag there instead of deploying new code, which is often the safer option.

## The canary

Once the deploy starts, the new version first goes to a canary. The canary receives 5% of
the traffic for 30 minutes. During this time you should keep an eye on the dashboards. If
everything looks fine after the 30 minutes, the rollout continues to the rest of the fleet
automatically, and you do not need to do anything else.

## If something goes wrong

If at any point the error rate goes above 0.5%, you should roll back right away. Do not
wait to see if it recovers on its own, because in our experience it usually does not. To
roll back, run `./scripts/rollback.sh --to previous`, which restores the previous version.

After you roll back, you should page the on-call engineer through the #ops-oncall channel
so that they are aware of the situation and can help investigate. The only exception to
this is a docs-only change: if your change only touched documentation, you do not need to
page anyone.

## Summary

To summarize: deploy only in the window, run the preflight, watch the canary, and roll back
quickly if the error rate climbs. Following these steps will keep our deploys safe.
