---
title: md2doc feature tour
subtitle: Markdown to PDF and PNG
author: Yotshiba
date: 2026-10-08
toc: 3
cover: false
---

# Feature tour

This document exercises everything `md2doc` supports: **text**, *emphasis*, ~~strikethrough~~, `inline code`,
[links](https://example.com), footnotes[^1], task lists, tables, images, LaTeX, Mermaid and PlantUML.

## Math

Inline math such as $E = mc^2$ and $\alpha + \beta = \gamma$ sits in a sentence. Money like $5 and $10 is left alone.

Display math:

$$
\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}
$$

An aligned system:

\begin{align}
  \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
  \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t}
\end{align}

Chemistry: $\ce{CO2 + H2O -> H2CO3}$

## Code

```python
def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

## Tables and lists

| Feature   | PDF | PNG |
|-----------|:---:|:---:|
| Math      | yes | yes |
| Mermaid   | yes | yes |
| PlantUML  | yes | yes |

- [x] Markdown parsing
- [x] Themes and fonts
- [ ] World domination

> [!NOTE]
> GitHub-style alerts are supported, as are `!!! tip` admonitions.

!!! tip "Tip"
    Use `--theme nord` or `--accent "#e91e63"` to change the look.

## Images

![A small generated image](sample.png "Figure 1: images are embedded, sized and captioned"){width=40%}

## Diagrams

```mermaid
flowchart LR
    A[Markdown] --> B{md2doc}
    B -->|PDF| C[Report.pdf]
    B -->|PNG| D[Poster.png]
    B --> E[(Themes)]
```

```mermaid
sequenceDiagram
    participant U as User
    participant C as CLI
    participant B as Browser
    U->>C: md2doc notes.md
    C->>B: render HTML
    B-->>C: PDF bytes
    C-->>U: notes.pdf
```

```plantuml
@startuml
actor User
participant "md2doc" as App
database Cache
User -> App : convert(notes.md)
App -> Cache : lookup diagrams
Cache --> App : miss
App --> User : notes.pdf
@enduml
```

[^1]: Footnotes are collected at the end of the document.
