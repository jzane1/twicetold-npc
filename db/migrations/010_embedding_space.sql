-- Bind this database to one embedding space. Existing vectors have unknown
-- provenance: migration deliberately leaves the singleton unbound. Startup
-- binds an empty store; legacy stores require explicit operator attestation.
CREATE TABLE embedding_space (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    configuration jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
