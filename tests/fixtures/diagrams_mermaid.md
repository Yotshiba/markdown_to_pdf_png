# Mermaid gallery

## Flowchart
```mermaid
flowchart TD
    A[Start] --> B{Valid?}
    B -- yes --> C[Process]
    B -- no --> D[Reject]
    C --> E((Done))
    subgraph Group
      C
      D
    end
```

## Sequence
```mermaid
sequenceDiagram
    participant A as Alice
    participant B as Bob
    A->>B: Hello
    activate B
    B-->>A: Hi
    deactivate B
    Note over A,B: A note
    loop Every minute
      A->>B: ping
    end
```

## Class
```mermaid
classDiagram
    class Animal {
      +String name
      +speak() void
    }
    class Dog
    Animal <|-- Dog
    Dog : +fetch()
```

## State
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> Idle : stop
    Running --> [*]
```

## ER
```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    CUSTOMER { string name }
```

## Journey
```mermaid
journey
    title My day
    section Morning
      Wake up: 3: Me
      Coffee: 5: Me, Cat
    section Work
      Code: 4: Me
```

## Gantt
```mermaid
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Build
    Design :a1, 2026-01-01, 7d
    Code   :after a1, 10d
    section Ship
    Release :milestone, 2026-02-01, 0d
```

## Pie
```mermaid
pie title Share
    "A" : 40
    "B" : 35
    "C" : 25
```

## Quadrant
```mermaid
quadrantChart
    title Reach
    x-axis Low --> High
    y-axis Low --> High
    quadrant-1 Expand
    quadrant-2 Promote
    quadrant-3 Re-evaluate
    quadrant-4 Improve
    Campaign A: [0.3, 0.6]
    Campaign B: [0.7, 0.2]
```

## Requirement
```mermaid
requirementDiagram
    requirement req1 {
      id: 1
      text: the system shall work
      risk: high
      verifymethod: test
    }
    element e1 {
      type: simulation
    }
    e1 - satisfies -> req1
```

## Git graph
```mermaid
gitGraph
    commit
    branch dev
    checkout dev
    commit
    checkout main
    merge dev
    commit tag: "v1"
```

## Mindmap
```mermaid
mindmap
  root((Ideas))
    Alpha
      One
      Two
    Beta
```

## Timeline
```mermaid
timeline
    title History
    2020 : Start
    2022 : Growth : More
    2024 : Scale
```

## Sankey
```mermaid
sankey-beta
Source,Mid,50
Mid,Out A,30
Mid,Out B,20
```

## XY chart
```mermaid
xychart-beta
    title "Sales"
    x-axis [jan, feb, mar]
    y-axis "Revenue" 0 --> 100
    bar [30, 60, 80]
    line [30, 60, 80]
```

## Block
```mermaid
block-beta
    columns 3
    a["A"] b["B"] c["C"]
    d["D"]:2 e["E"]
```

## Packet
```mermaid
packet-beta
    0-15: "Source Port"
    16-31: "Destination Port"
    32-63: "Sequence Number"
```

## Architecture
```mermaid
architecture-beta
    group api(cloud)[API]
    service db(database)[Database] in api
    service server(server)[Server] in api
    db:L -- R:server
```

## Kanban
```mermaid
kanban
  Todo
    t1[Write docs]
  Doing
    t2[Fix bug]
  Done
    t3[Ship]
```
