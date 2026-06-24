# cady Documentation

## Overview

Start here when you need more than the README. Each section gives a short
overview first, then the practical details.

## Details

## Section Index

| Section | Covers |
|---|---|
| [Getting started](getting-started.md) | Install, first model, exports, and reads. |
| [Object model](object-model.md) | Key objects, how they are created, and how they relate. |
| [New API sketch](../new-api.md) | Proposed simpler object model and representation rules. |
| [Architecture](architecture.md) | Package layout and dependency boundaries. |
| [API guide](api.md) | Public imports and common methods. |
| [File formats](files/index.md) | DXF, STL, STEP support and limits. |
| [Plotting and visualisation](visualisation.md) | Static plots and interactive viewing. |
| [Examples](examples.md) | Runnable scripts and gallery outputs. |
| [Development](development.md) | Setup, gates, and contribution rules. |

## Fast Paths

New users should read [Getting started](getting-started.md), then
[Object model](object-model.md), then [API guide](api.md).

Contributors should read [Architecture](architecture.md) and
[Development](development.md).

## Core Idea

cady keeps CAD authoring semantic:

```python
from cady import Model, circle, rectangle
```

Convert to arrays only at calculation, plotting, tessellation, or export
boundaries:

```text
domain.to_array(tolerance=...) -> ops function -> numeric result
```
