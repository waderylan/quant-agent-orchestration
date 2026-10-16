# GCS persistence alternative

Cloud Storage FUSE can back durable Cloud Run state if the application actually reads and writes it and the service identity has access. Claimed multi-turn state must survive instance replacement. [Project scope](../../project.md) currently treats each request as self-contained; choosing persistence requires an implementation and a deployed check.
