---
title: API rate limits
owner: platform
---

# API rate limits

## Overview

In this section we would like to give you an overview of how rate limiting works in our
public API. Rate limiting is something that every client integration will eventually run
into, so it is worth understanding it well up front. The good news is that the rules are
fairly simple once you have seen them laid out, and the table below does most of the work.

## Limits per plan

The limits depend on which plan the account is on. They are summarized in the following
table, which shows the number of requests per minute and the burst size for each plan.

| Plan | Requests per minute | Burst |
| --- | --- | --- |
| Free | 60 | 10 |
| Pro | 600 | 100 |
| Enterprise | 6000 | 1000 |

It is worth pointing out that the limits are applied per API key, and not per IP address.
This means that if you use several keys, each key has its own separate budget, and that
moving your traffic to a different IP address will not give you any additional capacity.

## What happens when you hit the limit

When you go over the limit, the API responds with a 429 status code. Every 429 response
includes a `Retry-After` header, which tells you how many seconds to wait before trying
again. Please make sure your client actually reads this header.

Clients are expected to back off exponentially. The back-off should start at 1 s and
double each time, and it should be capped at 64 s so that clients do not end up waiting
forever. Here is an example of what a well-behaved request looks like:

```bash
curl -sS https://api.example.com/v2/items \
  -H "Authorization: Bearer $API_KEY" \
  --retry 5 --retry-max-time 64
```

On the other hand, a 400 response is a completely different situation. A 400 means the
request itself is wrong, so you should never retry a 400, because retrying it will just
fail again in exactly the same way and waste part of your budget.

## Special cases

The batch endpoint, `/v2/batch`, is counted differently from the other endpoints. Instead
of counting each call as one request, it counts as 1 request per 100 items in the batch,
which makes it a lot cheaper when you have many items to send.

Webhooks, which we send to you, are not rate-limited at all, so you do not need to worry
about them in this context.

## Getting a higher limit

Enterprise customers who need more than their plan allows can request a raise by writing to
support@example.com. Please be aware that the request usually takes 5 business days to be
processed, so plan ahead and do not leave it to the last minute.
