# PlantUML gallery

## Sequence
```plantuml
@startuml
actor User
participant App
database DB
User -> App : request
App -> DB : query
DB --> App : rows
App --> User : response
@enduml
```

## Class
```plantuml
@startuml
class Animal {
  +name : string
  +speak()
}
class Dog
interface Pet
Animal <|-- Dog
Dog ..|> Pet
@enduml
```

## Use case
```plantuml
@startuml
left to right direction
actor Customer
rectangle Shop {
  Customer --> (Buy item)
  (Buy item) .> (Pay) : include
}
@enduml
```

## Activity
```plantuml
@startuml
start
:Read input;
if (valid?) then (yes)
  :Process;
else (no)
  :Reject;
endif
stop
@enduml
```

## Component
```plantuml
@startuml
package "Backend" {
  [API] --> [Service]
  [Service] --> [Repository]
}
database "Postgres" as pg
[Repository] --> pg
@enduml
```

## State
```plantuml
@startuml
[*] --> Idle
Idle --> Running : start
Running --> Idle : stop
Running --> [*]
@enduml
```

## Object
```plantuml
@startuml
object user {
  name = "Ada"
}
object order
user --> order
@enduml
```

## Deployment
```plantuml
@startuml
node "Server" {
  [Web] --> [App]
}
cloud "Internet"
Internet --> Web
@enduml
```

## Gantt
```plantuml
@startgantt
[Design] lasts 5 days
[Build] lasts 8 days
[Build] starts at [Design]'s end
@endgantt
```

## Mindmap
```plantuml
@startmindmap
* Root
** Left
*** Leaf
** Right
@endmindmap
```

## WBS
```plantuml
@startwbs
* Project
** Phase 1
*** Task A
** Phase 2
@endwbs
```

## JSON
```plantuml
@startjson
{"name": "md2doc", "tags": ["a", "b"], "n": 3}
@endjson
```

## Wireframe
```plantuml
@startsalt
{
  Login | "user   "
  Password | "****  "
  [Cancel] | [  OK  ]
}
@endsalt
```

## Skinparam by the author wins
```plantuml
@startuml
skinparam ParticipantBackgroundColor #ffd54f
Alice -> Bob : custom colour
@enduml
```
