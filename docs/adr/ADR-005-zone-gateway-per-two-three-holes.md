# ADR-005 — Zone Gateway per Approximately Two to Three Holes

## Context

The venue needs deterministic field scheduling, sensor I/O, timestamps, buffering, updates and manageable wiring. Direct field-node home runs or one SBC per hole create unnecessary complexity.

## Options

1. No Gateway; every node connects to Edge.
2. One Gateway per hole.
3. One Zone Gateway per 2–3 holes.
4. One Gateway for the whole venue.

## Decision

Choose option 3 as the production planning baseline. One Gateway per hole is allowed in the one-hole pilot. Final zone size is site- and load-verified.

## Why

- contains field timing and bus responsibility;
- limits fault domain without excessive hardware;
- supports two protected RS-485 branches and local 24 V zones;
- reduces Ethernet endpoints and Edge coupling;
- provides scheduling and outage buffering close to devices.

## Risks

A Gateway failure affects multiple holes; gateway sizing/scheduling may be underestimated.

## Validation

2–3-hole pilot, failure injection, P95 scheduler headroom >=40%, CPU/memory <60%, bounded buffering and replacement test.

## Revisit trigger

- cabling/site layout favours two or four holes per zone;
- gateway load/fault domain misses gates;
- a hole has unique machinery requiring independent controller;
- future connectionless architecture changes coordination needs.
