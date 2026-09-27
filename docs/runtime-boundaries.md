# Runtime boundaries

The canonical owner table is [Runtime ownership map](runtime-ownership-map.md). Use that table when
changing a state machine, store, or mutation path; this page keeps older links valid without
maintaining a second authority map.

The [system map](system-map.md) connects those owners to the execution flow, terminology, and
acceptance milestones. The [Rust migration plan](rust-first-harness.md) describes the destination,
not a second active owner.

A boundary-changing PR must name the owner, callers migrated, persisted/wire compatibility,
rollback path, duplicates removed or intentionally retained, and evidence that authority remains
singular. Storage implements domain/application ports; DAGs compose managed work; adapters own I/O.
